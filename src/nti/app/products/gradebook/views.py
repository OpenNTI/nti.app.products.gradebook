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

from nti.contenttypes.courses import interfaces as courses_interfaces

from nti.dataserver import authorization as nauth
from nti.dataserver import interfaces as nti_interfaces

from nti.utils._compat import aq_base
from nti.utils.maps import CaseInsensitiveDict

from . import utils
from . import gradescheme
from . import interfaces as grades_interfaces

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
@component.adapter(courses_interfaces.ICourseInstance, IRequest)
def GradeBookPathAdapter(context, request):
	result = grades_interfaces.IGradeBook(context)
	return result

@interface.implementer(IPathAdapter)
@component.adapter(courses_interfaces.ICourseInstance, IRequest)
def GradesPathAdapter(context, request):
	result = grades_interfaces.IGrades(context)
	return result

@view_config(context=grades_interfaces.IGrades)
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
	if	grades_interfaces.IGradeBookEntry.providedBy(obj):
		if obj.assignmentId and get_assignment(obj.assignmentId) is None:
			utils.raise_field_error(request,
									"assignmentId",
									_("must specify a valid grade assignment id"))
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

@view_config(context=grades_interfaces.IGrades)
@view_defaults(**_c_view_defaults)
class GradePostView(AbstractAuthenticatedView,
					ModeledContentUploadRequestUtilsMixin):

	def _do_call(self):
		creator = self.getRemoteUser()
		context = self.request.context
		externalValue = self.readInput()
		datatype = self.findContentType(externalValue)

		grade = self.createAndCheckContentObject(
									None, datatype, externalValue, creator,
									lambda x: grades_interfaces.IGrade.providedBy(x))
		self.updateContentObject(grade, externalValue, set_id=False, notify=False)

		gradebook = grades_interfaces.IGradeBook(context)
		if not grade.ntiid or gradebook.get_entry_by_ntiid(grade.ntiid) is None:
			utils.raise_field_error(self.request,
									"ntiid",
									_("must specify a valid grade entry ntiid"))

		context.add_grade(grade)

		self.request.response.status_int = 201 # created
		self.request.response.location = self.request.current_route_url(grade.username, grade.ntiid)

		return grade

@view_config(context=grades_interfaces.IGrades)
@view_defaults(**_u_view_defaults)
class GradesPutView(GradePostView):
	pass

@view_config(context=grades_interfaces.IGrades)
@view_defaults(**_d_view_defaults)
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

@view_config(context=grades_interfaces.IGrade)
@view_defaults(**_u_view_defaults)
class GradePutView(AbstractAuthenticatedView,
				   ModeledContentUploadRequestUtilsMixin,
				   ModeledContentEditRequestUtilsMixin):

	def _get_object_to_update(self):
		return self.request.context

	def __call__(self):
		theObject = self._get_object_to_update()
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue, set_id=False, notify=True)
		theObject.updateLastMod()

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
