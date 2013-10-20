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

from zope import lifecycleevent

from ZODB.interfaces import IConnection

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.appserver._view_utils import AbstractAuthenticatedView
from nti.appserver._view_utils import ModeledContentEditRequestUtilsMixin
from nti.appserver._view_utils import ModeledContentUploadRequestUtilsMixin
from nti.appserver.dataserver_pyramid_views import _GenericGetView as GenericGetView

from nti.dataserver import authorization as nauth
from nti.dataserver import interfaces as nti_interfaces

from nti.utils._compat import aq_base
from nti.utils.maps import CaseInsensitiveDict

from . import utils
from . import grades
from . import interfaces as grades_interfaces

_view_defaults = dict(  route_name='objects.generic.traversal',
						renderer='rest' )
_c_view_defaults = _view_defaults.copy()
_c_view_defaults.update( permission=nauth.ACT_CREATE,
						 request_method='POST' )
_u_view_defaults = _view_defaults.copy()
_u_view_defaults.update(permission=nauth.ACT_UPDATE,
						 request_method='PUT')
_r_view_defaults = _view_defaults.copy()
_r_view_defaults.update( permission=nauth.ACT_READ,
						 request_method='GET' )
_d_view_defaults = _view_defaults.copy()
_d_view_defaults.update( permission=nauth.ACT_DELETE,
						 request_method='DELETE' )

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

@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults(**_c_view_defaults)
class GradeBookPostView(AbstractAuthenticatedView,
					  	ModeledContentUploadRequestUtilsMixin):

	def _do_call(self):
		creator = self.getRemoteUser()
		context = self.request.context
		externalValue = self.readInput()
		datatype = self.findContentType(externalValue)

		containedObject = self.createAndCheckContentObject(None, datatype, externalValue, creator)
		containedObject.creator = creator

		owner_jar = IConnection(context)
		if owner_jar and getattr(containedObject, '_p_jar', self) is None:
			owner_jar.add( containedObject )

		self.updateContentObject(containedObject, externalValue, set_id=False, notify=False)

		lifecycleevent.created(containedObject)

		__traceback_info__ = containedObject
		assert containedObject.id

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
		# remove read only properties
		for name in ('EntryID', 'PartID', 'id'):
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

@view_config(context=grades_interfaces.IGrades)
@view_defaults(**_c_view_defaults)
class SetGradeView(AbstractAuthenticatedView,
				   ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		request = self.request
		values = CaseInsensitiveDict(**self.readInput())
		grade = grades.Grade()
		entryId = values.get('entryId')
		if not entryId:
			utils.raise_field_error(request, "entryid", _("must specify a valid grade entry"))
		grade.entryId = entryId
	
		value = values.get('grade')
		if value is None:
			utils.raise_field_error(request, "grade", _("must specify a valid grade"))

		try:
			field = grades_interfaces.IGrade['grade']
			value = field.fromUnicode(value)
			grade.grade = value
		except:
			utils.raise_field_error(request, "grade", _("must specify a valid grade"))

		username = values.get('username', values.get('student'))
		if not username:
			utils.raise_field_error(request, "username", _("must specify a valid student name"))

		store = request.context
		store.add_grade(username, grade)
		return hexc.HTTPNoContent()

del _view_defaults
del _u_view_defaults
del _c_view_defaults
del _r_view_defaults
del _d_view_defaults
