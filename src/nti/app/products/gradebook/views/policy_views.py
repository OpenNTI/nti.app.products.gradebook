#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView
from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.courses.grading import reset_grading_policy
from nti.contenttypes.courses.grading import set_grading_policy_for_course
from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

GRADING_POLICY = 'GradingPolicy'


class GradingPolicyMixin(object):

    @Lazy
    def course(self):
        return ICourseInstance(self.context)


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=GRADING_POLICY,
               permission=nauth.ACT_READ)
class CourseGradingPolicyGetView(AbstractAuthenticatedView,
                                 GradingPolicyMixin):

    def __call__(self):
        policy = find_grading_policy_for_course(self.course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy


@view_config(context=ICourseGradingPolicy)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_READ)
class GradingPolicyGetView(AbstractAuthenticatedView, GradingPolicyMixin):

    def __call__(self):
        return self.context


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=GRADING_POLICY,
               permission=nauth.ACT_UPDATE)
class CourseGradingPolicyPostView(UGDPostView, GradingPolicyMixin):

    content_predicate = ICourseGradingPolicy.providedBy

    def _do_call(self):
        creator = self.remoteUser
        policy = self.readCreateUpdateContentObject(creator,
                                                    search_owner=False)
        policy.creator = creator.username
        set_grading_policy_for_course(self.course, policy)
        lifecycleevent.created(policy)
        try:
            policy.validate()
        except ValueError as e:
            raise hexc.HTTPUnprocessableEntity(str(e))
        self.request.response.status_int = 201
        return policy


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               name=GRADING_POLICY,
               permission=nauth.ACT_UPDATE)
class CourseGradingPolicyPutView(UGDPutView, GradingPolicyMixin):

    def _get_object_to_update(self):
        policy = find_grading_policy_for_course(self.course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy

    def __call__(self):
        result = UGDPutView.__call__(self)  # modified event is raised
        try:
            result.validate()
        except ValueError as e:
            raise hexc.HTTPUnprocessableEntity(str(e))
        return result


@view_config(context=ICourseGradingPolicy)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_UPDATE)
class GradingPolicyPutView(CourseGradingPolicyPutView):

    def _get_object_to_update(self):
        return self.context


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               name=GRADING_POLICY,
               permission=nauth.ACT_UPDATE)
class CourseGradingPolicyDeleteView(UGDDeleteView, GradingPolicyMixin):

    def _get_object_to_delete(self):
        policy = find_grading_policy_for_course(self.course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy

    def _do_delete_object(self, obj):
        reset_grading_policy(self.course)
        lifecycleevent.removed(obj, self.course, None)
        return True

    def __call__(self):
        return UGDDeleteView.__call__(self)


@view_config(context=ICourseGradingPolicy)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_UPDATE)
class GradingPolicyDeleteView(UGDDeleteView, GradingPolicyMixin):

    def _do_delete_object(self, obj):
        reset_grading_policy(self.course)
        lifecycleevent.removed(obj, self.course, None)
        return True

    def __call__(self):
        return UGDDeleteView.__call__(self)
