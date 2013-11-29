#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade schemes

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.dataserver import mimetype

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.ILetterGradeScheme)
class LetterGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.ILetterGradeScheme)

	def __eq__(self, other):
		return self is other or grades_interfaces.ILetterGradeScheme.providedBy(other)

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.mimeType)
		return xhash

@interface.implementer(grades_interfaces.INumericGradeScheme)
class NumericGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.INumericGradeScheme)

	_type = float

	@classmethod
	def fromUnicode(cls, value):
		return cls._type(value)

	def validate(self, value):
		value = self._type(value)
		if value < self.min or value > self.max:
			raise ValueError("Invalid grade value")

	def __eq__(self, other):
		try:
			return self is other or (self.min == other.min and self.max == other.max)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.min)
		xhash ^= hash(self.max)
		return xhash
	
@interface.implementer(grades_interfaces.IIntegerGradeScheme)
class IntegerGradeScheme(NumericGradeScheme):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.IIntegerGradeScheme)

	_type = int

@interface.implementer(grades_interfaces.IBooleanGradeScheme)
class BooleanGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.IBooleanGradeScheme)

	@classmethod
	def fromUnicode(cls, value):
		return value.lower() in ('1', 'y', 't', 'yes', 'true')

	@classmethod
	def validate(cls, value):
		if not value in (True, False):
			raise ValueError("Invalid grade value")

	def __eq__(self, other):
		return self is other or grades_interfaces.IBooleanGradeScheme.providedBy(other)

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.mimeType)
		return xhash
