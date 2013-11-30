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
from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.ILetterGradeScheme)
class LetterGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	grades = FP(grades_interfaces.ILetterGradeScheme['grades'])

	default_grades = ('A', 'B', 'C', 'D', 'F')

	def __init__(self, grades=None,):
		super(LetterGradeScheme, self).__init__()
		self.grades = self.default_grades if grades is None else grades

	def fromUnicode(self, value):
		self.validate(value)
		return value

	def validate(self, value):
		if value.upper() in self.grades:
			raise ValueError("Invalid grade value")

	def __eq__(self, other):
		try:
			return self is other or (self.grades == other.grades)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.grades)
		return xhash

@interface.implementer(grades_interfaces.INumericGradeScheme)
class NumericGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.INumericGradeScheme)

	_type = float

	def fromUnicode(self, value):
		value = self._type(value)
		self.validate(value)
		return value

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

	true_values = ('1', 'y', 't', 'yes', 'true')
	false_values = ('0', 'n', 'f', 'no', 'false')

	@classmethod
	def fromUnicode(cls, value):
		if value.lower() in cls.true_values:
			value = True
		elif value.lower() in cls.false_values:
			value = False
		cls.validate(value)
		return value

	@classmethod
	def validate(cls, value):
		if value not in (True, False):
			raise ValueError("Invalid grade value")

	def __eq__(self, other):
		return self is other or grades_interfaces.IBooleanGradeScheme.providedBy(other)

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.mimeType)
		return xhash
