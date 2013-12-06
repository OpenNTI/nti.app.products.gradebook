#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade schemes

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import numbers

from zope import interface

from nti.dataserver import mimetype

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.ILetterGradeScheme)
class LetterGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	_type = six.string_types
	
	grades = FP(grades_interfaces.ILetterGradeScheme['grades'])
	ranges = FP(grades_interfaces.ILetterGradeScheme['ranges'])

	default_grades = ('A', 'B', 'C', 'D', 'F')
	default_ranges = ((90, 100), (80, 89), (70, 79), (60, 69), (0, 59))
	
	def __init__(self, grades=None, ranges=None):
		super(LetterGradeScheme, self).__init__()
		self.grades = self.default_grades if grades is None else grades
		self.ranges = self.default_ranges if ranges is None else ranges
		assert len(self.grades) == len(self.ranges)

	def toLetter(self, value):
		for i, r in enumerate(self.ranges):
			_min, _max = r
			if value >= _min and value <= _max:
				return self.grades[i]
		return None
		
	def fromUnicode(self, value):
		self.validate(value)
		return value

	def validate(self, value):
		if not isinstance(value, self._type):
			raise TypeError('wrong type')
		elif value.upper() in self.grades:
			raise ValueError("Invalid grade value")

	def __eq__(self, other):
		try:
			return self is other or (self.grades == other.grades
									 and self.ranges == other.ranges)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.grades)
		xhash ^= hash(self.ranges)
		return xhash

@interface.implementer(grades_interfaces.INumericGradeScheme)
class NumericGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.INumericGradeScheme)

	_type = numbers.Number

	def fromUnicode(self, value):
		value = float(value)
		self.validate(value)
		return value

	def validate(self, value):
		if not isinstance(value, self._type):
			raise TypeError('wrong type')
		elif value < self.min or value > self.max:
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

	_type = (int, long)
	
	def fromUnicode(self, value):
		value = int(value)
		self.validate(value)
		return value

@interface.implementer(grades_interfaces.IBooleanGradeScheme)
class BooleanGradeScheme(SchemaConfigured):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(grades_interfaces.IBooleanGradeScheme)

	_type  = bool
	
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
		if not isinstance(value, cls._type):
			raise TypeError('wrong type')

	def __eq__(self, other):
		return self is other or grades_interfaces.IBooleanGradeScheme.providedBy(other)

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.mimeType)
		return xhash
