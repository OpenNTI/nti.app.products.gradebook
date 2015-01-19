#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.location import locate
from zc.intid import IIntIds

from zope.catalog.interfaces import ICatalog
from zope.catalog.interfaces import ICatalogIndex

from nti.dataserver.interfaces import ICreatedUsername

from nti.zope_catalog.catalog import Catalog
from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import ValueIndex as RawValueIndex
from nti.zope_catalog.index import AttributeValueIndex as ValueIndex

from nti.zope_catalog.string import StringTokenNormalizer

from .interfaces import IGrade

CATALOG_NAME = 'nti.dataserver.++etc++gradebook-catalog'

IX_CREATOR = 'creator'
IX_USERNAME = 'username'
IX_GRADE_TYPE = 'gradeType'
IX_GRADE_VALUE = 'gradeValue'

class AssignmentIdIndex(ValueIndex):
	default_field_name = 'AssignmentId'
	default_interface = IGrade

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
		else:
			self.type = None

	def __reduce__(self):
		raise TypeError()

class GradeValueTypeIndex(ValueIndex):
	default_field_name = 'type'
	default_interface = ValidatingGradeValueType

@interface.implementer(ICatalog)
class GradeCatalog(Catalog):
	pass

def install_grade_catalog( site_manager_container, intids=None ):
	lsm = site_manager_container.getSiteManager()
	if intids is None:
		intids = lsm.getUtility(IIntIds)

	catalog = GradeCatalog(family=intids.family)
	catalog.__name__ = CATALOG_NAME
	catalog.__parent__ = site_manager_container
	intids.register( catalog )
	lsm.registerUtility(catalog, provided=ICatalog, name=CATALOG_NAME )

	for name, clazz in ( (IX_CREATOR, CreatorIndex),
						 (IX_USERNAME, UsernameIndex),
						 (IX_GRADE_VALUE, GradeValueIndex),
						 (IX_GRADE_TYPE, GradeValueTypeIndex) ):
		index = clazz( family=intids.family )
		assert ICatalogIndex.providedBy(index)
		intids.register( index )
		locate(index, catalog, name)
		catalog[name] = index

	return catalog
