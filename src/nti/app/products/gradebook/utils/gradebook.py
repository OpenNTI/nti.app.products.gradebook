# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from ZODB.interfaces import IConnection

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.event import notify

from zope.location.location import locate

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.courseware.interfaces import ICourseInstanceActivity

from nti.app.products.gradebook.assignments import synchronize_gradebook

from nti.app.products.gradebook.autograde_policies import find_autograde_policy_for_assignment_in_course

from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.grading import IGradeBookGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import GradeRemovedEvent

from nti.assessment.interfaces import IPlaceholderAssignmentSubmission

from nti.assessment.submission import AssignmentSubmission

from nti.assessment.assignment import QAssignmentSubmissionPendingAssessment

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dataserver.interfaces import IUser

logger = __import__('logging').getLogger(__name__)


def mark_btree_bucket_as_changed(grade):
    # Now, because grades are not persistent objects,
    # the btree bucket containing this grade has to be
    # manually told that its contents have changed.
    # Note that this is very expensive,
    # waking up each bucket of the tree.
    # pylint: disable=protected-access
    column = grade.__parent__
    btree = column._SampleContainer__data
    bucket = btree._firstbucket
    found = False
    while bucket is not None:
        if bucket.has_key(grade.__name__):
            bucket._p_changed = True
            if bucket._p_jar is None:  # The first bucket is stored special
                btree._p_changed = True
            found = True
            break
        bucket = bucket._next
    if not found:
        # before there are buckets, it might be inline data?
        btree._p_changed = True
    return found


def save_in_container(container, key, value, event=False):
    # pylint: disable=protected-access,too-many-function-args
    if event:
        container[key] = value
    else:
        container._setitemf(key, value)
        locate(value, parent=container, name=key)
        IConnection(container).add(value)
        lifecycleevent.added(value, container, key)
        try:
            container.updateLastMod()
        except AttributeError:
            pass
        container._p_changed = True


def remove_from_container(container, key, event=False):
    # pylint: disable=protected-access
    grade = container.get(key)
    user = IUser(grade, None)
    course = ICourseInstance(grade, None)
    assignment_id = getattr(grade, 'AssignmentId', None)
    if event:
        del container[key]
    else:
        # _delitemf calls ObjectEventRemoved
        container._delitemf(key)
        try:
            container.updateLastMod()
        except AttributeError:
            pass
        container._p_changed = True
    if grade is not None:
        notify(GradeRemovedEvent(grade, user, course, assignment_id))


def record_grade_without_submission(entry, user, assignmentId=None,
                                    clazz=PersistentGrade):
    # canonicalize the username in the event case got mangled
    username = user.username
    assignmentId = assignmentId or entry.AssignmentId

    # We insert the history item, which the user himself normally does
    # but cannot in this case. This implicitly creates the grade.
    # This is very similar to what nti.app.assessment.adapters
    # does for the student, just with fewer constraints...
    # The handling for a previously deleted grade is
    # what the subscriber does...this whole thing should be simplified
    submission = AssignmentSubmission()
    submission.assignmentId = assignmentId
    submission.creator = user
    interface.alsoProvides(submission, IPlaceholderAssignmentSubmission)

    grade = None
    course = ICourseInstance(entry)
    pending = QAssignmentSubmissionPendingAssessment(assignmentId=assignmentId,
                                                     parts=[])

    assignment_history = component.getMultiAdapter((course, submission.creator),
                                                   IUsersCourseAssignmentHistory)

    try:
        assignment_history.recordSubmission(submission, pending)
        # at this point a place holder grade is created we don't return it
        # to indicate to callers of this function that they need to get
        # the grade from the entry
    except KeyError:
        # In case there is already a submission (but no grade)
        # we need to deal with creating the grade object ourself.
        # This code path hits if a grade is deleted
        grade = clazz()
        save_in_container(entry, username, grade)
    else:
        # We don't want this phony-submission showing up as course activity
        # See nti.app.assessment.subscribers
        activity = ICourseInstanceActivity(course)
        # pylint: disable=too-many-function-args
        activity.remove(submission)
    return grade


def synchronize_gradebook_and_verify_policy(course, *unused_args, **unused_kwargs):
    synchronize_gradebook(course)
    # CS: We verify the grading policy after
    # the gradebook has been synchronized
    policy = find_grading_policy_for_course(course)
    if      policy is not None \
        and IGradeBookGradingPolicy.providedBy(policy) \
        and not policy.verify():
        entry = ICourseCatalogEntry(course)
        logger.error("There are errors in grading policy for course %s",
                     entry.ntiid)


def find_entry_for_item(item):
    assert IUsersCourseAssignmentHistoryItem.providedBy(item)
    assignmentId = item.Submission.assignmentId
    course = ICourseInstance(item, None)
    if course is None:
        # Typically during tests
        logger.warning("Assignment %s has no course", assignmentId)
        return None
    # pylint: disable=too-many-function-args
    book = IGradeBook(course)
    entry = book.getColumnForAssignmentId(assignmentId)
    if entry is None:
        # Typically during tests something is added
        synchronize_gradebook_and_verify_policy(course)
        entry = book.getColumnForAssignmentId(assignmentId)
    if entry is None:
        # Also typically during tests.
        logger.warning("Assignment %s not found in course %s",
                       assignmentId, course)
        return
    return entry


def set_grade_by_assignment_history_item(item, overwrite=False):
    entry = find_entry_for_item(item)
    if entry is not None:
        user = IUser(item)
        username = user.username
        if username in entry:
            grade = entry[username]
        else:
            grade = PersistentGrade()
            grade.username = username

        # If there is an auto-grading policy for the course instance,
        # then let it convert the auto-assessed part of the submission
        # into the initial grade value
        course = ICourseInstance(item)
        assignmentId = item.Submission.assignmentId
        policy = find_autograde_policy_for_assignment_in_course(course, assignmentId)
        if policy is not None:
            previous = grade.AutoGrade
            autograde = policy.autograde(item.pendingAssessment)
            if autograde is not None:
                grade.AutoGrade, grade.AutoGradeMax = autograde
            if grade.value is None or grade.value == previous or overwrite:
                grade.value = grade.AutoGrade

        if not getattr(grade, 'creator', None):
            grade.creator = SYSTEM_USER_ID

        if username in entry:
            lifecycleevent.modified(grade)
        else:
            # Finally after we finish filling it in, publish it
            save_in_container(entry, user.username, grade)
        return grade
    return None
