#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.catalog.interfaces import ICatalog

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.app.products.gradebook.interfaces import IGrade

from nti.common.string import to_unicode

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from nti.zope_catalog.catalog import Catalog

from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import ValueIndex as RawValueIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from nti.zope_catalog.interfaces import IMetadataCatalog

from nti.zope_catalog.string import StringTokenNormalizer

CATALOG_NAME = 'nti.dataserver.++etc++gradebook-catalog'

IX_SITE = 'site'
IX_GRADE_TYPE = 'gradeType'
IX_GRADE_VALUE = 'gradeValue'
IX_ASSIGNMENT_ID = 'assignmentId'
IX_STUDENT = IX_USERNAME = 'username'
IX_CREATOR = IX_INSTRUCTOR = 'creator'
IX_COURSE = IX_ENTRY = IX_GRADE_COURSE = 'gradeCourse'


class AssignmentIdIndex(ValueIndex):
    default_field_name = 'AssignmentId'
    default_interface = IGrade

    def index_doc(self, docid, obj):
        if not self.interface.providedBy(obj):
            return None
        return super(AssignmentIdIndex, self).index_doc(docid, obj)


class ValidatingGradeCreatorType(object):

    __slots__ = (b'creator',)

    def __init__(self, obj, default=None):
        if IGrade.providedBy(obj):
            creator = getattr(obj, 'creator', None)
            creator = getattr(creator, 'username', creator)
            creator = getattr(creator, 'id', creator)  # in case of a principal
            if creator:
                self.creator = to_unicode(creator.lower())

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
    default_field_name = 'value'
    default_interface = IGrade

    def index_doc(self, docid, obj):
        if not self.interface.providedBy(obj):
            return None
        return super(GradeValueIndex, self).index_doc(docid, obj)


class ValidatingGradeValueType(object):
    """
    The "interface" we adapt to to find the grade value type.
    """

    __slots__ = (b'type',)

    def __init__(self, obj, default=None):
        grade = IGrade(obj, default)
        value = getattr(grade, 'value', None)
        if value is not None:
            self.type = to_unicode(value.__class__.__name__)

    def __reduce__(self):
        raise TypeError()


class GradeValueTypeIndex(ValueIndex):
    default_field_name = 'type'
    default_interface = ValidatingGradeValueType


class ValidatingGradeSite(object):
    """
    The "interface" we adapt to to find the grade value course.
    """

    __slots__ = (b'site',)

    def __init__(self, obj, default=None):
        grade = IGrade(obj, default)
        folder = find_interface(grade, IHostPolicyFolder, strict=False)
        if folder is not None:
            self.site = to_unicode(folder.__name__)

    def __reduce__(self):
        raise TypeError()


class SiteIndex(ValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingGradeSite


class ValidatingGradeCatalogEntryID(object):
    """
    The "interface" we adapt to to find the grade value course.
    """

    __slots__ = (b'ntiid',)

    def __init__(self, obj, default=None):
        grade = IGrade(obj, default)
        course = find_interface(grade, ICourseInstance, strict=False)
        entry = ICourseCatalogEntry(course, None)  # entry is an annotation
        if entry is not None:
            self.ntiid = to_unicode(entry.ntiid)

    def __reduce__(self):
        raise TypeError()


class CatalogEntryIDIndex(ValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingGradeCatalogEntryID


@interface.implementer(IMetadataCatalog)
class MetadataGradeCatalog(Catalog):

    super_index_doc = Catalog.index_doc

    def index_doc(self, docid, ob):
        pass

    def force_index_doc(self, docid, ob):
        self.super_index_doc(docid, ob)


def install_grade_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = lsm.queryUtility(IMetadataCatalog, name=CATALOG_NAME)
    if catalog is not None:
        return catalog

    catalog = MetadataGradeCatalog(family=intids.family)
    locate(catalog, site_manager_container, CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog, provided=IMetadataCatalog, name=CATALOG_NAME)

    for name, clazz in ((IX_SITE, SiteIndex),
                        (IX_CREATOR, GradeCreatorIndex),
                        (IX_GRADE_VALUE, GradeValueIndex),
                        (IX_USERNAME, GradeUsernameIndex),
                        (IX_GRADE_TYPE, GradeValueTypeIndex),
                        (IX_ASSIGNMENT_ID, AssignmentIdIndex),
                        (IX_GRADE_COURSE, CatalogEntryIDIndex)):
        index = clazz(family=intids.family)
        intids.register(index)
        locate(index, catalog, name)
        catalog[name] = index

    return catalog

# deprecated
from zope.deprecation import deprecated

deprecated("GradeCatalog", "use MetadataGradeCatalog")
@interface.implementer(ICatalog)
class GradeCatalog(Catalog):
    pass


deprecated("CreatorRawIndex", "No longer used")
class CreatorRawIndex(RawValueIndex):
    pass


deprecated("CreatorIndex", "No longer used")
def CreatorIndex(family=None):
    return None
