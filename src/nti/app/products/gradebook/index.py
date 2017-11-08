#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.location import locate

import BTrees

from nti.app.products.gradebook.interfaces import IGrade

from nti.base._compat import text_

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from nti.zope_catalog.catalog import Catalog
from nti.zope_catalog.catalog import DeferredCatalog

from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import ValueIndex as RawValueIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from nti.zope_catalog.interfaces import IDeferredCatalog

from nti.zope_catalog.string import StringTokenNormalizer

CATALOG_NAME = 'nti.dataserver.++etc++gradebook-catalog'

IX_SITE = 'site'
IX_GRADE_TYPE = 'gradeType'
IX_GRADE_VALUE = 'gradeValue'
IX_ASSIGNMENT_ID = 'assignmentId'
IX_STUDENT = IX_USERNAME = 'username'
IX_CREATOR = IX_INSTRUCTOR = 'creator'
IX_COURSE = IX_ENTRY = IX_GRADE_COURSE = 'gradeCourse'

logger = __import__('logging').getLogger(__name__)


class AssignmentIdIndex(ValueIndex):
    default_interface = IGrade
    default_field_name = 'AssignmentId'

    def index_doc(self, docid, obj):
        if not self.interface.providedBy(obj):
            return None
        return super(AssignmentIdIndex, self).index_doc(docid, obj)


class ValidatingGradeCreatorType(object):

    __slots__ = ('creator',)

    def __init__(self, obj, unused_default=None):
        if IGrade.providedBy(obj):
            creator = getattr(obj, 'creator', None)
            creator = getattr(creator, 'username', creator)
            creator = getattr(creator, 'id', creator)  # in case of a principal
            if creator:
                self.creator = text_(creator.lower())

    def __reduce__(self):
        raise TypeError()


class GradeCreatorIndex(ValueIndex):
    default_field_name = 'creator'
    default_interface = ValidatingGradeCreatorType


class GradeUsernameRawIndex(RawValueIndex):
    pass
UsernameRawIndex = GradeUsernameRawIndex  # BWC


def GradeUsernameIndex(family=None):
    return NormalizationWrapper(field_name='Username',
                                interface=IGrade,
                                index=GradeUsernameRawIndex(family=family),
                                normalizer=StringTokenNormalizer())


UsernameIndex = GradeUsernameIndex  # BWC


class GradeValueIndex(ValueIndex):
    default_interface = IGrade
    default_field_name = 'value'

    def index_doc(self, docid, obj):
        if not self.interface.providedBy(obj):
            return None
        return super(GradeValueIndex, self).index_doc(docid, obj)


class ValidatingGradeValueType(object):
    """
    The "interface" we adapt to to find the grade value type.
    """

    __slots__ = ('type',)

    def __init__(self, obj, unused_default=None):
        if IGrade.providedBy(obj):
            value = getattr(obj, 'value', None)
            if value is not None:
                self.type = text_(value.__class__.__name__)

    def __reduce__(self):
        raise TypeError()


class GradeValueTypeIndex(ValueIndex):
    default_field_name = 'type'
    default_interface = ValidatingGradeValueType


class ValidatingGradeSite(object):
    """
    The "interface" we adapt to to find the grade value course.
    """

    __slots__ = ('site',)

    def __init__(self, obj, unused_default=None):
        if IGrade.providedBy(obj):
            folder = find_interface(obj, IHostPolicyFolder, strict=False)
            if folder is not None:
                self.site = text_(folder.__name__)

    def __reduce__(self):
        raise TypeError()


class SiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingGradeSite


class ValidatingGradeCatalogEntryID(object):
    """
    The "interface" we adapt to to find the grade value course.
    """

    __slots__ = ('ntiid',)

    def __init__(self, obj, unused_default=None):
        if IGrade.providedBy(obj):
            course = find_interface(obj, ICourseInstance, strict=False)
            entry = ICourseCatalogEntry(course, None)  # entry is an annotation
            if entry is not None:
                self.ntiid = text_(entry.ntiid)

    def __reduce__(self):
        raise TypeError()


class CatalogEntryIDIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingGradeCatalogEntryID


@interface.implementer(IDeferredCatalog)
class MetadataGradeCatalog(DeferredCatalog):

    family = BTrees.family64

    def force_index_doc(self, docid, ob): # BWC
        self.index_doc(docid, ob)


def get_grade_catalog(registry=component):
    return registry.queryUtility(IDeferredCatalog, name=CATALOG_NAME)


def create_grade_catalog(catalog=None, family=BTrees.family64):
    if catalog is None:
        catalog = MetadataGradeCatalog(family=family)
    for name, clazz in ((IX_SITE, SiteIndex),
                        (IX_CREATOR, GradeCreatorIndex),
                        (IX_GRADE_VALUE, GradeValueIndex),
                        (IX_USERNAME, GradeUsernameIndex),
                        (IX_GRADE_TYPE, GradeValueTypeIndex),
                        (IX_ASSIGNMENT_ID, AssignmentIdIndex),
                        (IX_GRADE_COURSE, CatalogEntryIDIndex)):
        index = clazz(family=family)
        locate(index, catalog, name)
        catalog[name] = index

    return catalog


def install_grade_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = get_grade_catalog(lsm)
    if catalog is not None:
        return catalog

    catalog = create_grade_catalog(family=intids.family)
    locate(catalog, site_manager_container, CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog, 
                        provided=IDeferredCatalog, 
                        name=CATALOG_NAME)

    for index in catalog.values():
        intids.register(index)
    return catalog


# deprecated
from zope.deprecation import deprecated


deprecated("GradeCatalog", "No longer used")
class GradeCatalog(Catalog):
    pass


deprecated("CreatorRawIndex", "No longer used")
class CreatorRawIndex(RawValueIndex):
    pass


deprecated("CreatorIndex", "No longer used")
def CreatorIndex(_=None):
    return None
