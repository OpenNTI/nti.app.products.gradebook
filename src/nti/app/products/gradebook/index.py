#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.intid import IIntIds

from zope.location import locate

from zope.catalog.interfaces import ICatalog
from zope.catalog.interfaces import ICatalogIndex

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import ICreatedUsername

from nti.traversal.traversal import find_interface

from nti.zope_catalog.catalog import Catalog

from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import ValueIndex as RawValueIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from nti.zope_catalog.interfaces import IMetadataCatalog

from nti.zope_catalog.string import StringTokenNormalizer

from .interfaces import IGrade

CATALOG_NAME = 'nti.dataserver.++etc++gradebook-catalog'

IX_GRADE_TYPE = 'gradeType'
IX_GRADE_VALUE = 'gradeValue'
IX_GRADE_COURSE = 'gradeCourse'
IX_ASSIGNMENT_ID = 'assignmentId'
IX_STUDENT = IX_USERNAME = 'username'
IX_CREATOR = IX_INSTRUCTOR = 'creator'

class AssignmentIdIndex(ValueIndex):
	default_field_name = 'AssignmentId'
	default_interface = IGrade

	def index_doc(self, docid, obj):
		if not self.interface.providedBy(obj):
			return None
		return super(AssignmentIdIndex, self).index_doc(docid, obj)

class CreatorRawIndex(RawValueIndex):
	pass

def CreatorIndex(family=None):
	return NormalizationWrapper(field_name='creator_username',
								interface=ICreatedUsername,
								index=CreatorRawIndex(family=family),
								normalizer=StringTokenNormalizer())

class UsernameRawIndex(RawValueIndex):
	pass

def UsernameIndex(family=None):
	return NormalizationWrapper(field_name='Username',
								interface=IGrade,
								index=UsernameRawIndex(family=family),
								normalizer=StringTokenNormalizer())

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
			self.type = unicode(value.__class__.__name__)

	def __reduce__(self):
		raise TypeError()

class GradeValueTypeIndex(ValueIndex):
	default_field_name = 'type'
	default_interface = ValidatingGradeValueType

class ValidatingGradeCatalogEntryID(object):
	"""
	The "interface" we adapt to to find the grade value course.
	"""

	__slots__ = (b'ntiid',)

	def __init__(self, obj, default=None):
		grade = IGrade(obj, default)
		course = find_interface(grade, 
								ICourseInstance, 
								strict=False) if grade is not None else None
		entry = ICourseCatalogEntry(course, None)  # entry is an annotation
		if entry is not None:
			self.ntiid = unicode(entry.ntiid)

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
	if intids is None:
		intids = lsm.getUtility(IIntIds)

	catalog = lsm.queryUtility(IMetadataCatalog, name=CATALOG_NAME)
	if catalog is not None:
		return catalog

	catalog = MetadataGradeCatalog(family=intids.family)
	locate(catalog, site_manager_container, CATALOG_NAME)
	intids.register(catalog)
	lsm.registerUtility(catalog, provided=IMetadataCatalog, name=CATALOG_NAME)

	for name, clazz in ((IX_CREATOR, CreatorIndex),
						(IX_USERNAME, UsernameIndex),
						(IX_GRADE_VALUE, GradeValueIndex),
						(IX_GRADE_TYPE, GradeValueTypeIndex),
						(IX_ASSIGNMENT_ID, AssignmentIdIndex),
						(IX_GRADE_COURSE, CatalogEntryIDIndex)):
		index = clazz(family=intids.family)
		assert ICatalogIndex.providedBy(index)
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
