#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

import simplejson

from zope import component
from zope import interface
from zope import lifecycleevent
from zope.traversing.interfaces import IPathAdapter

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid.interfaces import IRequest
from pyramid import httpexceptions as hexc

from nti.appserver._view_utils import AbstractAuthenticatedView
from nti.appserver._view_utils import ModeledContentEditRequestUtilsMixin
from nti.appserver._view_utils import ModeledContentUploadRequestUtilsMixin
from nti.appserver.dataserver_pyramid_views import _GenericGetView as GenericGetView

from nti.assessment import interfaces as asm_interfaces

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth
from nti.dataserver import interfaces as nti_interfaces

from nti.ntiids import ntiids
from nti.utils._compat import aq_base
from nti.utils.maps import CaseInsensitiveDict

from . import utils
from . import gradescheme
from . import interfaces as grades_interfaces
from .interfaces import IGrade

_view_defaults = dict(route_name='objects.generic.traversal',
					  renderer='rest')
_c_view_defaults = _view_defaults.copy()
_c_view_defaults.update( permission=nauth.ACT_CREATE,
						 request_method='POST' )
_u_view_defaults = _view_defaults.copy()
_u_view_defaults.update(permission=nauth.ACT_UPDATE,
						request_method='PUT')
_r_view_defaults = _view_defaults.copy()
_r_view_defaults.update(permission=nauth.ACT_READ,
						request_method='GET')
_d_view_defaults = _view_defaults.copy()
_d_view_defaults.update(permission=nauth.ACT_DELETE,
						request_method='DELETE')

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter(context, request):
	result = grades_interfaces.IGradeBook(context)
	return result

@view_config(context=grades_interfaces.IGradeBook)
@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults( **_r_view_defaults )
class GradeBookGetView(GenericGetView):
	pass

@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults(**_d_view_defaults)
class GradeBookDeleteView(AbstractAuthenticatedView,
					  	  ModeledContentEditRequestUtilsMixin):

	def __call__(self):
		theObject = self.request.context
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)
		lastModified = theObject.lastModified

		base_parent = aq_base(theObject.__parent__)
		theObject.__dict__['__parent__'] = base_parent
		del base_parent[theObject.__name__]

		result = hexc.HTTPNoContent()
		result.last_modified = lastModified
		return result

def get_assignment(aid):
	return component.queryUtility(asm_interfaces.IQAssignment, name=aid)

def _validate_grade_entry(request, obj):
	if grades_interfaces.IGradeBookEntry.providedBy(obj):
		if obj.assignmentId and get_assignment(obj.assignmentId) is None:
			utils.raise_field_error(request,
									"assignmentId",
									_("must specify a valid grade assignment id"))

	if grades_interfaces.IGradeBookEntry.providedBy(obj):

		if obj.GradeScheme is None:
			obj.GradeScheme = gradescheme.NumericGradeScheme()

	if not obj.Name and not obj.displayName:
		utils.raise_field_error(request,
								"Name",
								_("must specify a valid name or display name"))

@view_config(context=grades_interfaces.IGradeBook)
@view_config(context=grades_interfaces.IGradeBookPart)
@view_defaults(**_c_view_defaults)
class GradeBookPostView(AbstractAuthenticatedView,
					  	ModeledContentUploadRequestUtilsMixin):

	def _do_call(self):
		context = self.request.context
		creator = self.getRemoteUser()
		containedObject = self.readCreateUpdateContentObject(creator)
		_validate_grade_entry(self.request, containedObject)

		if not containedObject.displayName:
			containedObject.displayName = containedObject.Name

		if not containedObject.Name:
			containedObject.Name = containedObject.displayName

		lifecycleevent.created(containedObject)

		containedObject.Name = ntiids.escape_provider(containedObject.Name)
		context[containedObject.Name] = containedObject

		self.request.response.status_int = 201  # created
		self.request.response.location = self.request.resource_path(containedObject)

		return containedObject

@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults(**_u_view_defaults)
class GradeBookPutView(AbstractAuthenticatedView,
					   ModeledContentUploadRequestUtilsMixin,
					   ModeledContentEditRequestUtilsMixin):


	def _get_object_to_update(self):
		try:
			return self.request.context.resource
		except AttributeError:
			if nti_interfaces.IZContained.providedBy(self.request.context):
				return self.request.context
			raise

	def readInput(self):
		externalValue = super(GradeBookPutView, self).readInput()
		for name in ('id', 'NTIID', 'GradeScheme', 'DueDate', 'Name'):
			if name in externalValue:
				del externalValue[name]
		return externalValue

	def __call__(self):
		theObject = self._get_object_to_update()
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue)

		return theObject

	def updateContentObject(self, theObject, external, *args, **kwargs):
		result = super(GradeBookPutView, self).updateContentObject(theObject, external)
		_validate_grade_entry(self.request, result)
		return result


class GradesDeleteView(AbstractAuthenticatedView):

	def readInput(self):
		request = self.request
		value = request.body
		value = simplejson.loads(unicode(value, request.charset))
		return CaseInsensitiveDict(value)

	def __call__(self):
		context = self.request.context
		externalValue = self.readInput()
		ntiid = externalValue.get('ntiid')
		username = externalValue.get('username')
		if context.remove_grade(ntiid, username):
			result = hexc.HTTPNoContent()
			result.last_modified = context.lastModified
		else:
			result = hexc.HTTPNotFound()
		return result

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
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue)
		theObject.updateLastMod()

		# Now, because grades are not persistent objects,
		# the btree bucket containing this grade has to be
		# manually told that its contents have changed.
		# XXX: Note that this is very expensive,
		# waking up each bucket of the tree.

		column = theObject.__parent__
		btree = column._SampleContainer__data
		bucket = btree._firstbucket
		found = False
		while bucket is not None:
			if bucket.has_key(theObject.__name__):
				bucket._p_changed = True
				if bucket._p_jar is None: # The first bucket is stored special
					btree._p_changed = True
				found = True
				break
			bucket = bucket._next
		if not found:
			# before there are buckets, it might be inline data?
			btree._p_changed = True

		return theObject

@view_config(context=grades_interfaces.IGrade)
@view_defaults(**_d_view_defaults)
class GradeDelView(AbstractAuthenticatedView,
				   ModeledContentEditRequestUtilsMixin):

	def __call__(self):
		context = self.request.context
		self._check_object_unmodified_since(context)

		grades = context.__parent__
		grades.remove_grade(context)

		result = hexc.HTTPNoContent()
		result.last_modified = grades.lastModified
		return result

del _view_defaults
del _u_view_defaults
del _c_view_defaults
del _r_view_defaults
del _d_view_defaults

from nti.externalization.interfaces import LocatedExternalDict
from nti.contenttypes.courses.interfaces import is_instructed_by_name

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=grades_interfaces.ISubmittedAssignmentHistory,
			 permission=nauth.ACT_READ)
class SubmittedAssignmentHistoryGetView(AbstractAuthenticatedView):

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = ICourseInstance(context)

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		result['Items'] = dict(context)
		column = context.__parent__
		result.__parent__ = column
		result.__name__ = context.__name__

		return result
