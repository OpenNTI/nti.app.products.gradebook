#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.dataserver import authorization as nauth

from ..interfaces import IGradeBook
from ..interfaces import IGradeScheme
from ..interfaces import IGradeBookEntry
from ..interfaces import IUsernameSortSubstitutionPolicy

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

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IDataserverFolder

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.utils.maps import CaseInsensitiveDict

def _tx_string(s):
    if s is not None and isinstance(s, unicode):
        s = s.encode('utf-8')
    return s

def _replace(username):
    substituter = component.queryUtility(IUsernameSortSubstitutionPolicy)
    if substituter is None:
        return username
    result = substituter.replace(username) or username
    return result

@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDataserverFolder,
             permission=nauth.ACT_NTI_ADMIN,
             name='CourseGrades')
class CourseGradesView(AbstractAuthenticatedView):
    
    def __call__(self):
        params = CaseInsensitiveDict(self.request.params)
        
        ntiid = params.get('ntiid') or \
                params.get('entry') or \
                params.get('course')
        if not ntiid:
            raise hexc.HTTPUnprocessableEntity(detail=_('No course entry identifier'))

        context = find_object_with_ntiid(ntiid)
        entry = ICourseCatalogEntry(context, None)
        if entry is None:
            try:
                catalog = component.getUtility(ICourseCatalog)
                entry = catalog.getCatalogEntry(ntiid)
            except LookupError:
                raise hexc.HTTPUnprocessableEntity(detail=_('Catalog not found'))
            except KeyError:
                raise hexc.HTTPUnprocessableEntity(detail=_('Course not found'))

        bio = BytesIO()
        csv_writer = csv.writer(bio)
        
        # header
        header = ['part', 'username', 'name', 'value'] 
        csv_writer.writerow(header)
        
        course = ICourseInstance(entry)
        book  = IGradeBook(course)
        for part_name, part in list(book.items()):
            for name, entry in list(part.items()):
                for username, grade in list(entry.items()):
                    name = grade.assignmentId
                    value = _tx_string(grade.value)
                    value = str(value) if value is not None else ''
                    row_data = [part_name, _replace(username), name, value]
                    csv_writer.writerow([_tx_string(x) for x in row_data])

        response = self.request.response
        response.body = bio.getvalue()
        response.content_disposition = b'attachment; filename="grades.csv"'
        return response
