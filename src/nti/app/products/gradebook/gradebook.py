#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade book definition

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.traversal import lineage

import six

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations
from zope.annotation.interfaces import IAttributeAnnotatable

from zope.cachedescriptors.property import CachedProperty

from zope.container.contained import Contained

from zope.container.interfaces import INameChooser

from zope.mimetype.interfaces import IContentTypeAware

from nti.app.assessment.common.history import get_most_recent_history_item

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookPart
from nti.app.products.gradebook.interfaces import IGradeBookEntry
from nti.app.products.gradebook.interfaces import NTIID_TYPE_GRADE_BOOK
from nti.app.products.gradebook.interfaces import NTIID_TYPE_GRADE_BOOK_PART
from nti.app.products.gradebook.interfaces import NTIID_TYPE_GRADE_BOOK_ENTRY
from nti.app.products.gradebook.interfaces import ISubmittedAssignmentHistory
from nti.app.products.gradebook.interfaces import ISubmittedAssignmentHistorySummaries

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentDateContext

from nti.containers.containers import AbstractNTIIDSafeNameChooser
from nti.containers.containers import CheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.users import User

from nti.externalization.representation import WithRepr

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids import ntiids

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.traversal.traversal import find_interface
from nti.app.assessment.common.policy import get_policy_submission_priority,\
    is_most_recent_submission_priority

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IContentTypeAware)
class _NTIIDMixin(object):

    parameters = {}

    _ntiid_type = None
    _ntiid_include_self_name = False
    _ntiid_default_provider = u'NextThought'

    @property
    def _ntiid_provider(self):
        return self._ntiid_default_provider

    @property
    def _ntiid_specific_part(self):
        try:
            parts = []
            for location in lineage(self):
                if IGradeBook.providedBy(location):
                    continue
                parts.append(ntiids.make_specific_safe(location.__name__))
                if ICourseInstance.providedBy(location):
                    break
            parts.reverse()
            result = None
            if None not in parts:
                result = '.'.join(parts)
            return result
        except AttributeError:  # Not ready yet
            return None

    @CachedProperty('_ntiid_provider', '_ntiid_specific_part')
    def NTIID(self):
        provider = self._ntiid_provider
        if provider and self._ntiid_specific_part:
            return ntiids.make_ntiid(date=ntiids.DATE,
                                     provider=provider,
                                     nttype=self._ntiid_type,
                                     specific=self._ntiid_specific_part)


@component.adapter(ICourseInstance)
@interface.implementer(IGradeBook, IAttributeAnnotatable)
class GradeBook(CheckingLastModifiedBTreeContainer,
                Contained,
                _NTIIDMixin):

    mimeType = mime_type = MIME_BASE + '.gradebook'

    _ntiid_type = NTIID_TYPE_GRADE_BOOK

    def getColumnForAssignmentId(self, assignmentId, check_name=False):
        for part in self.values():
            entry = part.get_entry_by_assignment(assignmentId,
                                                 check_name=check_name)
            if entry is not None:
                return entry
        return None
    get_entry_by_assignment = getEntryByAssignment = getColumnForAssignmentId

    def getEntryByNTIID(self, ntiid):
        result = None
        type_ = ntiids.get_type(ntiid)
        if type_ == NTIID_TYPE_GRADE_BOOK_ENTRY:
            specific = ntiids.get_specific(ntiid)
            part, entry = specific.split('.')[-2:]
            result = self.get(part, {}).get(entry)
        return result
    get_entry_by_ntiid = getEntryByNTIID

    def remove_user(self, username):
        result = 0
        for part in self.values():
            if part.remove_user(username):
                result += 1
        return result
    removeUser = remove_user

    @property
    def Items(self):
        return dict(self)

    def has_grades(self, username):
        for part in self.values():
            if part.has_grades(username):
                return True
        return False

    def iter_grades(self, username):
        for part in self.values():
            for grade in part.iter_grades(username):
                yield grade

    def iter_usernames(self):
        seen = set()
        for part in tuple(self.values()):
            for username in part.iter_usernames():
                if username not in seen:
                    seen.add(username)
                    yield username


@interface.implementer(IGradeBook)
@component.adapter(ICourseInstance)
def gradebook_for_course(course, create=True):
    result = None
    KEY = u'GradeBook'
    annotations = IAnnotations(course)
    try:
        result = annotations[KEY]
    except KeyError:
        if create:
            result = GradeBook()
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
            # Deterministically add to our course db.
            # pylint: disable=too-many-function-args
            connection = IConnection(course, None)
            if connection is not None:
                connection.add(result)
    return result
_gradebook_for_course = gradebook_for_course


@WithRepr
@EqHash('NTIID',)
@interface.implementer(IGradeBookEntry, IAttributeAnnotatable)
class GradeBookEntry(SchemaConfigured,
                     # Warning !!!! This is wrong, this should be a Case/INSENSITIVE/ btree,
                     # usernames are case insensitive. Everyone that uses this this
                     # has to be aware and can't do the usual thing of lower-casing for their
                     # own comparisons. Until we do a database migration we partially
                     # ameliorate this for __contains__ (at the cost of a performance penalty),
                     # but we can't completely
                     CheckingLastModifiedBTreeContainer,
                     Contained,
                     _NTIIDMixin):

    mimeType = mime_type = MIME_BASE + '.gradebookentry'

    _ntiid_include_self_name = True
    _ntiid_type = NTIID_TYPE_GRADE_BOOK_ENTRY

    createDirectFieldProperties(IGradeBookEntry)

    Name = alias('__name__')

    ntiid = alias('NTIID')
    gradeScheme = alias('GradeScheme')

    assignmentId = alias('AssignmentId')

    def __init__(self, **kwargs):
        # SchemaConfigured is not cooperative
        CheckingLastModifiedBTreeContainer.__init__(self)
        SchemaConfigured.__init__(self, **kwargs)

    def __setstate__(self, state):
        super(GradeBookEntry, self).__setstate__(state)
        if '_SampleContainer__data' not in self.__dict__:
            self._SampleContainer__data = self._newContainerData()

    @property
    def _gbe_len(self):
        return len(self)

    @CachedProperty('_gbe_len')
    def _lower_keys_to_upper_key(self):
        # Caching based on the length isn't exactly correct, as an add
        # followed by a delete will be missed. However, we don't have a pattern
        # that does that, and it's much cheaper than calculating a set of the
        # usernames
        return {k.lower(): k for k in self.keys()}

    def __contains__(self, key):
        result = super(GradeBookEntry, self).__contains__(key)
        if not result and key and isinstance(key, six.string_types):
            # Sigh, long expensive path
            # pylint: disable=unsupported-membership-test
            result = key.lower() in self._lower_keys_to_upper_key
        return result
    has_key = __contains__

    def __getitem__(self, key):
        try:
            return super(GradeBookEntry, self).__getitem__(key)
        except KeyError:
            if not key or not isinstance(key, six.string_types):
                raise
            # Sigh, long expensive path
            # pylint: disable=no-member
            upper = self._lower_keys_to_upper_key.get(key.lower())
            if upper and upper != key:  # careful not to infinite recurse
                return self.__getitem__(upper)
            raise

    def __delitem__(self, key):
        try:
            return super(GradeBookEntry, self).__delitem__(key)
        except KeyError:
            if not key or not isinstance(key, six.string_types):
                raise
            # Sigh, long expensive path
            # pylint: disable=no-member
            upper = self._lower_keys_to_upper_key.get(key.lower())
            if upper and upper != key:  # careful not to infinite recurse
                return self.__delitem__(upper)
            raise

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    @property
    def Items(self):
        return dict(self)

    @property
    def DueDate(self):
        asg = component.queryUtility(IQAssignment,
                                     name=self.assignmentId or '')
        course = ICourseInstance(self, None)
        return get_assignment_due_date(asg, course)

    @DueDate.setter
    def DueDate(self, value=None):
        pass

    def __str__(self):
        return self.displayName


def get_assignment_due_date(assignment, course):
    if course is not None and assignment is not None:
        datecontext = IQAssignmentDateContext(course)
        # pylint: disable=too-many-function-args
        return datecontext.of(assignment).available_for_submission_ending
    return None


@WithRepr
@interface.implementer(IGradeBookPart, IAttributeAnnotatable)
class GradeBookPart(SchemaConfigured,
                    CheckingLastModifiedBTreeContainer,
                    Contained,
                    _NTIIDMixin):

    mimeType = mime_type = MIME_BASE + '.gradebookpart'

    _ntiid_include_self_name = True
    _ntiid_type = NTIID_TYPE_GRADE_BOOK_PART

    createDirectFieldProperties(IGradeBookPart)

    __name__ = alias('Name')

    entryFactory = GradeBookEntry

    def __init__(self, **kwargs):
        # SchemaConfigured is not cooperative
        CheckingLastModifiedBTreeContainer.__init__(self)
        SchemaConfigured.__init__(self, **kwargs)

    def validateAssignment(self, unused_assignment):
        return True

    def getEntryByAssignment(self, assignmentId, check_name=False):
        for entry in self.values():
            if     entry.assignmentId == assignmentId \
                or (check_name and entry.__name__ == assignmentId):
                return entry
        return None
    get_entry_by_assignment = getEntryByAssignment

    def remove_user(self, username):
        result = 0
        username = username.lower()
        for entry in tuple(self.values()):
            if username in entry:
                try:
                    del entry[username]
                    result += 1
                except KeyError:
                    # in alpha we have seen key errors even though
                    # the membership check has been made
                    logger.exception("Error deleting grade for %s in entry %s",
                                     username, entry.__name__)
        return result
    removeUser = remove_user

    @property
    def Items(self):
        return dict(self)

    def has_grades(self, username):
        username = username.lower()
        for entry in tuple(self.values()):
            if username in entry:
                return True
        return False

    def iter_grades(self, username):
        # FIXME: rethink this
        from nti.app.products.gradebook.utils.gradebook import get_applicable_user_grade
        username = username.lower()
        for entry in tuple(self.values()):
            if username in entry:
                grade = get_applicable_user_grade(entry, username)
                if grade is not None:
                    yield grade

    def iter_usernames(self):
        seen = set()
        for entry in tuple(self.values()):
            for username in tuple(entry.keys()):
                if username not in seen:
                    seen.add(username)
                    yield username

    def __str__(self):
        return self.displayName


from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.interfaces import IGradeWithoutSubmission


@interface.implementer(IGradeWithoutSubmission)
class GradeWithoutSubmission(PersistentGrade):
    """
    A dummy grade we temporarily create before
    a submission comes in.
    """
    __external_class_name__ = 'Grade'
    __external_can_create__ = False


PersistentGradeWithoutSubmission = NoSubmitGradeBookEntryGrade = GradeWithoutSubmission


class GradeBookEntryWithoutSubmission(GradeBookEntry):
    """
    An entry in the gradebook that doesn't necessarily require
    students to already have a submission.
    """
    __external_class_name__ = 'GradeBookEntry'
    __external_can_create__ = False

    mimeType = mime_type = MIME_BASE + '.gradebook.gradebookentry'


NoSubmitGradeBookEntry = GradeBookEntryWithoutSubmission

from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.traversal.traversal import ContainerAdapterTraversable


class GradeBookEntryWithoutSubmissionTraversable(ContainerAdapterTraversable):
    """
    Entries that cannot be submitted by students auto-generate
    :class:`.GradeWithoutSubmission` objects (that they own but do not contain)
    when directly traversed to during request processing.

    We do this at request traversal time, rather than as part of the
    the get/__getitem__ method of the class, to not break any of the container
    assumptions.

    In general, prefer to register this only for special named parts; it is dangerous
    as a main traversal mechanism because of the possibility of blocking
    student submissions and the wide-ranging consequences of interfering
    with traversal.
    """

    def traverse(self, name, furtherPath):  # pylint: disable=arguments-differ
        try:
            return super(GradeBookEntryWithoutSubmissionTraversable, self).traverse(name, furtherPath)
        except KeyError:
            # Check first for items in the container and named adapters.
            # Only if that fails do we dummy up a grade,
            # and only then if there is a real user by that name
            # who is enrolled in this course.
            user = User.get_user(name)
            if not user:
                raise
            course = ICourseInstance(self.context)
            course_enrollments = ICourseEnrollments(course)
            # pylint: disable=too-many-function-args
            if course_enrollments.get_enrollment_for_principal(user):
                result = GradeWithoutSubmission()
                result.__parent__ = self.context
                result.__name__ = name
                return result
            raise


class NoSubmitGradeBookPart(GradeBookPart):
    """
    A special part of the gradebook for those things that
    cannot be submitted by students, only entered by the
    instructor. These assignments are validated as such.

    We use a special entry; see :class:`.NoSubmitGradeBookEntry`
    for details.
    """

    __external_class_name__ = 'GradeBookPart'
    mimeType = mime_type = MIME_BASE + '.gradebook.gradebookpart'

    entryFactory = GradeBookEntryWithoutSubmission

    def validateAssignment(self, assignment):
        # pylint: disable=unused-variable
        __traceback_info__ = assignment
        if not assignment.no_submit:
            raise ValueError(assignment.category_name)
        if len(assignment.parts) != 0:
            raise ValueError("Too many parts")
        return True


_NotGiven = object()


def _entry_submitted_length(self):
    # By directly using this API and (not the adapter interface) and
    # setting create to False, in a large course with many users but few
    # submissions, we gain a significant performance improvement if we
    # iterate across the entire list: 9 or 10x (This is because
    # creating---and then discarding when we abort the GET request
    # transaction---all those histories is expensive, requesting new OIDs
    # from the database and firing lots of events). I'm not formalizing
    # this API yet because we shouldn't be iterating across and
    # materializing the entire list; if we can make that stop we won't
    # need this.
    from nti.app.assessment.adapters import _histories_for_course

    count = 0
    column = self.context
    course = ICourseInstance(self)
    assignment_id = column.AssignmentId
    histories = _histories_for_course(course)
    # do count
    for history in list(histories.values()):
        if assignment_id in history:
            count += 1
    return count


@component.adapter(IGradeBookEntry)
@interface.implementer(ISubmittedAssignmentHistory)
class _DefaultGradeBookEntrySubmittedAssignmentHistory(Contained):

    __name__ = 'SubmittedAssignmentHistory'

    # We don't externalize this item, but we do create links to it,
    # and they want a mimeType
    mimeType = 'application/json'

    as_summary = False

    def __init__(self, entry, unused_request=None):
        self.context = self.__parent__ = entry

    def __conform__(self, iface):
        if ICourseInstance.isOrExtends(iface):
            return find_interface(self, ICourseInstance)
        if IGradeBookEntry.isOrExtends(iface):
            return self.context

    @property
    def lastModified(self):
        """
        Our last modified time is the time the column was modified
        by addition/removal of a grade.
        """
        return self.context.lastModified

    def __bool__(self):
        return True
    __nonzero__ = __bool__

    def __len__(self):
        """
        Getting the length of this object is extremely slow and should
        be avoided.

        The length is defined as the number of people that have submitted
        to the assignment; this is distinct from the number of grades that may
        exist, and much more expensive to compute.
        """
        result = _entry_submitted_length(self)
        return result

    def __iter__(self,
                 usernames=_NotGiven,
                 placeholder=_NotGiven,
                 forced_placeholder_usernames=None):

        from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemSummary

        column = self.context
        course = ICourseInstance(self)
        assignment_id = column.AssignmentId
        if usernames is _NotGiven:
            usernames = column
        if not forced_placeholder_usernames:
            forced_placeholder_usernames = ()

        # ensure we have a set (for speed) that we can be case-insensitive on
        # (for correctness)
        forced_placeholder_usernames = {
            x.lower() for x in forced_placeholder_usernames
        }

        for username_that_submitted in usernames or ():
            username_that_submitted = username_that_submitted.lower()

            if username_that_submitted in forced_placeholder_usernames:
                yield (username_that_submitted, placeholder)
                continue

            user = User.get_user(username_that_submitted)
            if not IUser.providedBy(user):
                continue
            username_that_submitted = user.username  # go back to canonical
            # TODO: Do we need this view at all?
            # TODO: This is approximate
            history_item = get_most_recent_history_item(user, course, assignment_id)
            if history_item is not None:
                if self.as_summary:
                    history_item = IUsersCourseAssignmentHistoryItemSummary(history_item)
                yield (username_that_submitted, history_item)
            else:
                if placeholder is not _NotGiven:
                    yield (username_that_submitted, placeholder)

    def items(self,
              usernames=_NotGiven,
              placeholder=_NotGiven,
              forced_placeholder_usernames=None):
        """
        Return an iterator over the items (username, submission_container)
        that make up this object. This is just like iterating over
        this object normally, except the option of filtering.

        :keyword usernames: If given, an iterable of usernames.
                Only usernames that are in this iterable are returned.
                Furthermore, the items are returned in the same order
                as the usernames in the iterable. Note that if the username
                doesn't exist, nothing is returned for that entry
                unless `placeholder` is also provided.
        :keyword placeholder: If given (even if given as None)
                then all users in `usernames` will be returned; those
                that have not submitted will be returned with this placeholder
                value. This only makes sense if usernames is given.
        :keyword forced_placeholder_usernames: If given and not None, a container of usernames
                that define a subset of `usernames` that will return the
                placeholder, even if they did have a submission. Obviously
                this only makes sense if a placeholder is defined. This can make
                iteration faster if you know that only some subset of the usernames
                will actually be looked at (e.g., a particular numerical range).
        """
        if placeholder is not _NotGiven and usernames is _NotGiven:
            raise ValueError("Placeholder only makes sense if usernames is given")

        if forced_placeholder_usernames is not None and placeholder is _NotGiven:
            raise ValueError("Ignoring users only works with a ploceholder")

        return self.__iter__(usernames=usernames,
                             placeholder=placeholder,
                             forced_placeholder_usernames=forced_placeholder_usernames)

    def __getitem__(self, username):
        """
        We are traversable to users
        """
        (username, item), = self.items(usernames=(username,), placeholder=None)
        if item is not None:
            return item
        raise KeyError(username)


@interface.implementer(ISubmittedAssignmentHistorySummaries)
@component.adapter(IGradeBookEntry)
class _DefaultGradeBookEntrySubmittedAssignmentHistorySummaries(_DefaultGradeBookEntrySubmittedAssignmentHistory):
    __name__ = 'SubmittedAssignmentHistorySummaries'
    as_summary = True


@component.adapter(IGradeBookPart)
@interface.implementer(INameChooser)
class _GradeBookPartNameChooser(AbstractNTIIDSafeNameChooser):
    """
    Handles NTIID-safe name choosing for gradebook entry.
    """
    leaf_iface = IGradeBookPart
