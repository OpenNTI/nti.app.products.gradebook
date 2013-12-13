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
from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from nti.dataserver import mimetype

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

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
		
	def toNumber(self, letter):
		try:
			index = self.grades.index(letter.upper())
			_, _max = self.ranges[index]
			return _max
		except ValueError:
			pass
		return None

	def _max_in_ranges(self):
		result = max(self.ranges[0])
		for r in self.ranges[1:]:
			result = max(result, *r)
		return result

	def _min_in_ranges(self):
		result = min(self.ranges[0])
		for r in self.ranges[1:]:
			result = min(result, *r)
		return result

	def toCorrectness(self, letter):
		dem = self._max_in_ranges()
		num = self.toNumber(letter)
		return num / float(dem)
	
	def fromCorrectness(self, value):
		dem = float(self._max_in_ranges())
		for i, r in enumerate(self.ranges):
			_min, _max = r
			if value >= (_min / dem) and value <= (_max / dem):
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

class ExtendedLetterGradeScheme(LetterGradeScheme):
	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	default_grades = ('A+', 'A', 'A-',
					  'B+', 'B', 'B-',
					  'C+', 'C', 'C-',
					  'D', 'D', 'F')

	default_ranges = ((90, 100), (86, 89), (80, 85),
					  (77, 79),  (73, 76), (70, 72),
					  (67, 69),  (63, 66), (60, 62),
					  (57, 59),  (50, 56), (0, 49))

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

	def toCorrectness(self, value):
		result = (value - self.min) / float(self.max - self.min)
		return result if result > 0 else 0.0

	def fromCorrectness(self, value):
		result = value * (self.max - self.min) + self.min
		return result

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

	def toCorrectness(self, value):
		result = 1.0 if value else 0.0
		return result

	def fromCorrectness(self, value):
		result = value >= 0.999
		return result

	def __eq__(self, other):
		return self is other or grades_interfaces.IBooleanGradeScheme.providedBy(other)

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.mimeType)
		return xhash
