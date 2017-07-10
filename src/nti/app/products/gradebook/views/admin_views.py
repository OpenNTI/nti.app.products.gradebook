#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import csv
import six
from io import BytesIO

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.gradebook.assignments import synchronize_gradebook

from nti.app.products.gradebook.index import get_grade_catalog

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeScheme
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.app.products.gradebook.utils import replace_username

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.site.hostpolicy import get_all_host_sites

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


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
        theObject.creator = self.getRemoteUser().username
        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)
        externalValue = self.readInput()
        theObject.GradeScheme = externalValue
        return theObject


def _tx_string(s):
    if s is not None and isinstance(s, six.text_type):
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


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='CourseGrades')
class CourseGradesView(AbstractAuthenticatedView):

    def __call__(self):
        course = ICourseInstance(self.context)
        params = CaseInsensitiveDict(self.request.params)
        usernames = params.get('usernames') or params.get('username')
        if usernames:
            usernames = {x.lower() for x in usernames.split(',')}

        bio = BytesIO()
        csv_writer = csv.writer(bio)

        # header
        header = ['username', 'part', 'entry', 'assignment', 'grade']
        csv_writer.writerow(header)

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
                    row_data = [replace_username(username), 
								part_name, name,
                                assignmentId, value]
                    csv_writer.writerow([_tx_string(x) for x in row_data])

        response = self.request.response
        response.body = bio.getvalue()
        response.content_disposition = 'attachment; filename="grades.csv"'
        return response


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='SynchronizeGradebook')
class SynchronizeGradebookView(AbstractAuthenticatedView,
                               ModeledContentUploadRequestUtilsMixin):

    def __call__(self):
        course = ICourseInstance(self.context)
        synchronize_gradebook(self.context)
        result = LocatedExternalDict()
        items = result[ITEMS] = {}
        book = IGradeBook(course, None)
        if book is not None:
            for part_name, part in book.items():
                items.setdefault(part_name, [])
                for entry_name in part.keys():
                    items[part_name].append(entry_name)
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildGradeCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildGradeCatalogView(AbstractAuthenticatedView):

    def _process_meta(self, grade):
        try:
            from nti.metadata import queue_add
            queue_add(grade)
        except ImportError:
            pass

    def _process_course(self, course, catalog, intids):
        count = 0
        book = IGradeBook(course, None)
        if book is not None:
            for part in list(book.values()):  # parts
                for entry in list(part.values()):  # entries
                    for grade in list(entry.values()):  # grades
                        doc_id = intids.queryId(grade)
                        if doc_id is not None:
                            catalog.index_doc(doc_id, grade)
                            self._process_meta(grade)
                            count += 1
        return count

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        catalog = get_grade_catalog()
        for index in catalog.values():
            index.clear()
        # reindex
        total = 0
        seen = set()
        for host_site in get_all_host_sites():  # check all sites
            logger.info("Processing site %s", host_site.__name__)
            with current_site(host_site):
                catalog = component.queryUtility(ICourseCatalog)
                if catalog is None or catalog.isEmpty():
                    continue
                for entry in catalog.iterCatalogEntries():
                    course = ICourseInstance(entry)
                    doc_id = intids.queryId(course)
                    if doc_id is None or doc_id in seen:
                        continue
                    seen.add(doc_id)
                    total += self._process_course(course, catalog, intids)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = result[TOTAL] = total
        return result
