# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from ZODB.interfaces import IConnection

from zope import lifecycleevent

from zope.event import notify

from zope.location.location import locate

from nti.app.assessment.common.policy import is_most_recent_submission_priority

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.gradebook.assignments import synchronize_gradebook

from nti.app.products.gradebook.autograde_policies import find_autograde_policy_for_assignment_in_course

from nti.app.products.gradebook.gradebook import numeric_grade_val

from nti.app.products.gradebook.grades import GradeContainer
from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import GradeRemovedEvent

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

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
    """
    Create a grade and store as the MetaGrade on the grade container.
    """
    # canonicalize the username in the event case got mangled
    username = user.username
    assignmentId = assignmentId or entry.AssignmentId

    if username in entry:
        grade_container = entry[username]
    else:
        grade_container = GradeContainer()
        # XXX: Why no event?
        save_in_container(entry, user.username, grade_container)

    grade = clazz()
    grade.__parent__ = grade_container
    grade_container.MetaGrade = grade
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
    """
    For the given :class:`IUsersCourseAssignmentHistoryItem`, set the grade in
    the gradebook. If we are configured to auto_grade, auto_grade and either
    store that value in the gradebook (if the policy specifies we accept the
    `most_recent` submission) or compare it versus the current gradebook value
    if it exists (if the policy specifies we accept the `highest_grade`
    submission).

    Now that we have multiple submissions, we'll store this new grade *in addition*
    to any existing grades that are already in play. We'll rely on any submission
    constraints to also apply to constraining our grade container size (e.g. we will
    not concern ourselves with that here).

    :returns the grade object if exists
    """
    entry = find_entry_for_item(item)
    if entry is not None:
        user = IUser(item)
        username = user.username
        if username in entry:
            grade_container = entry[username]
        else:
            grade_container = GradeContainer()
            # XXX: Why no event?
            save_in_container(entry, user.username, grade_container)

        if item.ntiid in grade_container:
            # XX: Should this even be possible?
            grade = grade_container[username]
        else:
            grade = PersistentGrade()
            grade.username = username
            grade_container[item.ntiid] = grade

        # If there is an auto-grading policy for the course instance,
        # then let it convert the auto-assessed part of the submission
        # into the initial grade value
        course = ICourseInstance(item)
        assignmentId = item.Submission.assignmentId
        policy = find_autograde_policy_for_assignment_in_course(course, assignmentId)
        if policy is not None:
            # Check priority
            most_recent = is_most_recent_submission_priority(assignmentId, course)
            autograde_res = policy.autograde(item.pendingAssessment)
            if autograde_res is not None:
                grade.AutoGrade, grade.AutoGradeMax = autograde_res

            # Take our current grade if we do not have a current grade
            # - or if they are equal (grade.value = previous_grade.AutoGrade) (now removed)
            # - or forced
            # - or if we must accept most recent
            # Take the current grade if we want the highest graded submission
            # and our new grade is higher than the previous grade
            numeric_val = numeric_grade_val(grade.value)
            if grade.value is None or overwrite or most_recent:
                grade.value = grade.AutoGrade
            elif not most_recent and grade.AutoGrade and grade.AutoGrade > numeric_val:
                # We're configured to only override if our new grade is higher
                grade.value = grade.AutoGrade

        if not getattr(grade, 'creator', None):
            grade.creator = SYSTEM_USER_NAME

        if item.ntiid in grade_container:
            lifecycleevent.modified(grade)
        else:
            # Finally after we finish filling it in, publish it
            # XXX: Why no event?
            save_in_container(grade_container, item.ntiid, grade)
        return grade
    return None
