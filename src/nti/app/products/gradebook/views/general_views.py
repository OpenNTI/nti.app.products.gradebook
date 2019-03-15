#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import lifecycleevent

from zope.annotation import IAnnotations

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from pyramid import httpexceptions as hexec

from pyramid.view import view_config

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemContainer

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeContainer
from nti.app.products.gradebook.interfaces import IGradeWithoutSubmission

from nti.app.products.gradebook.utils import record_grade_without_submission

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.assessment.interfaces import IQAssignment

from nti.coremetadata.interfaces import IUser

from nti.contenttypes.completion.interfaces import UserProgressRemovedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGradeBook,
             name='SetGrade',
             request_method='POST')
class GradeBookPutView(AbstractAuthenticatedView,
                       ModeledContentUploadRequestUtilsMixin,
                       ModeledContentEditRequestUtilsMixin):
    """
    Allows end users to set arbitrary grades in the gradebook,
    returning the assignment history item.

    Any edits directly on the gradebook end up being stored as the
    grade container MetaGrade, which takes precedence over all
    other grades for this user and assignment.
    """

    def _do_call(self):
        gradebook = self.context
        params = CaseInsensitiveDict(self.readInput())

        username = params.get('Username')
        new_grade_value = params.get('Value')
        assignment_ntiid = params.get('AssignmentId')

        user = User.get_user(username)
        if user is None:
            raise_json_error(self.request,
                             hexec.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"User not found."),
                             },
                             None)

        assignment = component.queryUtility(IQAssignment,
                                            name=assignment_ntiid)
        if assignment is None:
            raise_json_error(self.request,
                             hexec.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Assignment not found."),
                             },
                             None)

        asg_name = assignment.__name__
        gradebook_entry = gradebook.getColumnForAssignmentId(asg_name)
        if gradebook_entry is None:
            raise_json_error(self.request,
                             hexec.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Entry not found."),
                             },
                             None)

        # This will create our grade and assignment history, if necessary.
        grade = record_grade_without_submission(gradebook_entry,
                                                user,
                                                assignment_ntiid)

        # Check our if-modified-since header
        self._check_object_unmodified_since(grade)

        grade.creator = self.getRemoteUser().username
        grade.value = new_grade_value

        # If we get this far, we've modified a new or
        # previously existing grade and need to broadcast.
        notify(ObjectModifiedEvent(grade))

        logger.info("'%s' updated gradebook assignment '%s' for user '%s'",
                    self.getRemoteUser(),
                    assignment_ntiid,
                    username)

        # Not ideal that we return this here.
        history_item = IUsersCourseAssignmentHistoryItemContainer(grade)
        return history_item

@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGradeContainer,
             request_method='PUT')
class GradeContainerPutView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin,
                            ModeledContentEditRequestUtilsMixin):
    """
    When PUTing a grade to the container, this stores the MetaGrade,
    which superseeds all other grade values in the container.
    """

    content_predicate = IGrade.providedBy

    def _do_call(self):
        params = CaseInsensitiveDict(self.readInput())
        new_grade_value = params.get('Value')
        gradebook_entry = self.context.__parent__
        user = IUser(self.context)
        # This will create our meta grade, if necessary.
        grade = record_grade_without_submission(gradebook_entry,
                                                user,
                                                self.context.AssignmentId)

        # Check our if-modified-since header
        self._check_object_unmodified_since(grade)
        grade.creator = self.getRemoteUser().username
        grade.value = new_grade_value
        notify(ObjectModifiedEvent(grade))

        logger.info("'%s' updated gradebook assignment '%s' for user '%s'",
                    self.getRemoteUser(),
                    self.context.AssignmentId,
                    self.context.Username)
        return grade


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGrade,
             request_method='PUT')
class GradePutView(AbstractAuthenticatedView,
                   ModeledContentUploadRequestUtilsMixin,
                   ModeledContentEditRequestUtilsMixin):

    content_predicate = IGrade.providedBy

    def _do_call(self):
        theObject = self.request.context
        theObject.creator = self.getRemoteUser().username

        # perform checks
        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)

        # update from external
        externalValue = self.readInput()
        self.updateContentObject(theObject, externalValue)

        logger.info("'%s' updated grade '%s' for user '%s'",
                    self.getRemoteUser(),
                    theObject.AssignmentId,
                    theObject.Username)

        return theObject


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGrade,
             name="excuse",
             request_method='POST')
class ExcuseGradeView(AbstractAuthenticatedView,
                      ModeledContentUploadRequestUtilsMixin,
                      ModeledContentEditRequestUtilsMixin):
    """
    Deprecated: the container itself should hold excused state.
    """

    content_predicate = IGrade.providedBy

    def _do_call(self):
        theObject = self.request.context
        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)

        grade_container = self.context.__parent__

        grade_container.Excused = True
        grade_container.updateLastMod()
        notify(ObjectModifiedEvent(grade_container))
        return theObject


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGradeWithoutSubmission,
             name="excuse",
             request_method='POST')
class ExcuseGradeWithoutSubmissionView(ExcuseGradeView):
    """
    Deprecated: the container itself should hold excused state.
    """

    def _do_call(self):
        entry = self.request.context.__parent__
        username = self.request.context.__name__
        user = User.get_user(username)
        grade = record_grade_without_submission(entry, user)
        self.request.context = grade
        result = super(ExcuseGradeWithoutSubmissionView, self)._do_call()
        return result


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGrade,
             name="unexcuse",
             request_method='POST')
class UnexcuseGradeView(AbstractAuthenticatedView,
                        ModeledContentUploadRequestUtilsMixin,
                        ModeledContentEditRequestUtilsMixin):
    """
    Deprecated: the container itself should hold excused state.
    """

    content_predicate = IGrade.providedBy

    def _do_call(self):
        theObject = self.request.context
        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)

        grade_container = theObject.__parent__

        if grade_container.Excused:
            grade_container.Excused = False
            grade_container.updateLastMod()
            notify(ObjectModifiedEvent(grade_container))

            user = IUser(theObject, None)
            # Tests
            if user is None:
                return
            assignment = find_object_with_ntiid(theObject.AssignmentId)
            course = ICourseInstance(theObject)
            notify(UserProgressRemovedEvent(assignment,
                                            user,
                                            course))
        return theObject


@view_config(route_name='objects.generic.traversal',
             permission=nauth.ACT_UPDATE,
             renderer='rest',
             context=IGradeWithoutSubmission,
             request_method='PUT')
class GradeWithoutSubmissionPutView(GradePutView):
    """
    Called to put to a grade that doesn't yet exist.

    This should store a MetaGrade for our user and assignment.
    """

    # : We don't want extra catching of key errors
    _EXTRA_INPUT_ERRORS = ()

    def _do_call(self):
        # So we make one exist
        entry = self.request.context.__parent__
        username = self.request.context.__name__
        user = User.get_user(username)

        grade = record_grade_without_submission(entry, user)
        if grade is not None:
            # place holder grade was inserted (MetaGrade)
            self.request.context = grade
        else:
            # This inserted the 'real' grade. To actually
            # updated it with the given values, let the super
            # class do the work
            self.request.context = entry[username]

        result = super(GradeWithoutSubmissionPutView, self)._do_call()
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='DELETE',
             context=IGradeBook,
             permission=nauth.ACT_DELETE)
class GradebookDeleteView(UGDDeleteView):
    """
    Admins can delete an entire gradebook. This is mostly
    for migration purposes from old databases.
    """

    def _do_delete_object(self, context):
        # We happen to know that it is stored as an annotation.
        annots = IAnnotations(context.__parent__)
        del annots[context.__name__]
        lifecycleevent.removed(context)
        return True


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='DELETE',
             context=IGrade,
             permission=nauth.ACT_DELETE)
class GradeDeleteView(UGDDeleteView):
    """
    Instructors can delete an individual grade.
    """

    def _do_delete_object(self, context):
        # delete the grade from its grade container
        # One would think that if we got here it's because
        # there is actually a grade recorded so `del` would be
        # safe; one would be wrong. That's because of
        # ..gradebook.GradeBookEntryWithoutSubmissionTraversable which
        # dummies up a grade for anyone that asks. So if we can't find
        # it, follow the contract and let a 404 error be raised

        # We used to hide events here; I'm unsure why.
        container = context.__parent__
        try:
            del container[context.__name__]
        except KeyError:
            if context.__name__ == 'MetaGrade':
                container.MetaGrade = None
                result = True
            else:
                result = False
        else:
            result = True
        return result
