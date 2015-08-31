#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields

from ..utils import replace_username

from ..interfaces import IGradeBook
from ..interfaces import IGradeScheme
from ..interfaces import IGradeBookEntry

ITEMS = StandardExternalFields.ITEMS

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='PUT',
			 context=IGradeBookEntry,
			 permission=nauth.ACT_UPDATE)
class SetGradeSchemeView(AbstractAuthenticatedView,
						 ModeledContentEditRequestUtilsMixin,
						 ModeledContentUploadRequestUtilsMixin):

	content_predicate = IGradeScheme.providedBy

	def _do_call(self):
		theObject = self.request.context
		theObject.creator = self.getRemoteUser()

		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		theObject.GradeScheme = externalValue

		return theObject

import csv
from io import BytesIO

from zope import component

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IDataserverFolder

from nti.ntiids.ntiids import find_object_with_ntiid

def _tx_string(s):
	if s is not None and isinstance(s, unicode):
		s = s.encode('utf-8')
	return s

def _tx_grade(value):
	if not isinstance(value, six.string_types):
		return value
	if value.endswith('-'):
		value = value[:-1].strip()
		for func in (int, float):
			try:
				return func(value)
			except ValueError:
				pass
		return _tx_string(value)

def _catalog_entry(params):
	ntiid = params.get('ntiid') or \
			params.get('entry') or \
			params.get('course')
	if not ntiid:
		raise hexc.HTTPUnprocessableEntity('No course entry identifier')

	context = find_object_with_ntiid(ntiid)
	entry = ICourseCatalogEntry(context, None)
	if entry is None:
		try:
			catalog = component.getUtility(ICourseCatalog)
			entry = catalog.getCatalogEntry(ntiid)
		except LookupError:
			raise hexc.HTTPUnprocessableEntity('Catalog not found')
		except KeyError:
			entry = None
	return entry

from nti.app.products.courseware.views import CourseAdminPathAdapter

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='CourseGrades')
class CourseGradesView(AbstractAuthenticatedView):

	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		entry = _catalog_entry(params)
		if entry is None:
			raise hexc.HTTPUnprocessableEntity(detail=_('Course not found'))

		usernames = params.get('usernames') or params.get('username')
		if usernames:
			usernames = usernames.split(',')
			usernames = {x.lower() for x in usernames}

		bio = BytesIO()
		csv_writer = csv.writer(bio)

		# header
		header = ['username', 'part', 'entry', 'assignment', 'grade']
		csv_writer.writerow(header)

		course = ICourseInstance(entry)
		book = IGradeBook(course)
		for part_name, part in list(book.items()):
			for name, entry in list(part.items()):
				for username, grade in list(entry.items()):
					username = username.lower()
					if usernames and username not in usernames:
						continue
					assignmentId = grade.assignmentId
					value = _tx_grade(grade.value)
					value = value if value is not None else ''
					row_data = [replace_username(username), part_name, name,
								assignmentId, value]
					csv_writer.writerow([_tx_string(x) for x in row_data])

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="grades.csv"'
		return response

from nti.externalization.interfaces import LocatedExternalDict

from ..assignments import synchronize_gradebook

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='SynchronizeGradebook')
class SynchronizeGradebookView(AbstractAuthenticatedView,
							   ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		params = CaseInsensitiveDict(self.readInput())
		entry = _catalog_entry(params)
		if entry is None:
			raise hexc.HTTPUnprocessableEntity(detail='Course not found')

		synchronize_gradebook(entry)

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		book = IGradeBook(ICourseInstance(entry, None), None)
		if book is not None:
			for part_name, part in book.items():
				items.setdefault(part_name, [])
				for entry_name in part.keys():
					items[part_name].append(entry_name)
		return result
