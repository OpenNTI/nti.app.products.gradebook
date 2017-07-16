#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects


def course_gradebook_objects(course):
    book = IGradeBook(ICourseInstance(course, None), None)
    if book is not None:
        yield book
        for part in book.values():
            yield part
            for entry in part.values():
                yield entry
                for grade in entry.valuues():
                    yield grade


@component.adapter(IUser)
class _GradePrincipalObjects(BasePrincipalObjects):

    def iter_objects(self):
        result = []
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return result
        for entry in catalog.iterCatalogEntries():
            for obj in course_gradebook_objects(entry):
                if IGrade.providedBy(obj) and self.creator(obj) == self.username:
                    result.append(obj)
        return result


@component.adapter(ISystemUserPrincipal)
class _GradeBookPrincipalObjects(BasePrincipalObjects):

    def iter_objects(self):
        result = []
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return result
        for entry in catalog.iterCatalogEntries():
            for obj in course_gradebook_objects(entry):
                if IGrade.providedBy(obj):
                    if self.is_system_username(self.creator(obj)):
                        result.append(obj)
                else:
                    result.append(obj)
        return result
