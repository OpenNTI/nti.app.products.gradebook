#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grade schemes

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import numbers

from zope import interface

from zope.mimetype.interfaces import IContentTypeAware

from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from nti.app.products.gradebook.interfaces import ILetterGradeScheme
from nti.app.products.gradebook.interfaces import IBooleanGradeScheme
from nti.app.products.gradebook.interfaces import IIntegerGradeScheme
from nti.app.products.gradebook.interfaces import INumericGradeScheme
from nti.app.products.gradebook.interfaces import ITotalPointsGradeScheme
from nti.app.products.gradebook.interfaces import ILetterNumericGradeScheme

from nti.app.products.gradebook.utils import MetaGradeBookObject

from nti.common.string import TRUE_VALUES
from nti.common.string import FALSE_VALUES

from nti.externalization.representation import WithRepr

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured

from nti.schema.fieldproperty import createDirectFieldProperties


@WithRepr
@EqHash('grades', 'ranges')
@interface.implementer(ILetterGradeScheme, IContentTypeAware)
class LetterGradeScheme(SchemaConfigured):

    __metaclass__ = MetaGradeBookObject

    _type = six.string_types

    grades = FP(ILetterGradeScheme['grades'])
    ranges = FP(ILetterGradeScheme['ranges'])

    default_grades = (u'A', u'B', u'C', u'D', u'F')
    default_ranges = ((90, 100), (80, 89), (70, 79), (40, 69), (0, 39))

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

    def fromCorrectness(self, grade):
        value = getattr(grade, 'RawValue', grade)
        value = (min(max(0, value), 1))
        dem = float(self._max_in_ranges())
        for i, r in enumerate(self.ranges):
            _min, _max = r
            if value >= (_min / dem) and value <= (_max / dem):
                return self.grades[i]
        return None

    def toDisplayableGrade(self, grade):
        return self.fromCorrectness(grade)

    def fromUnicode(self, value):
        self.validate(value)
        return value

    def validate(self, value):
        if value and value.endswith('-'):
            value = value[:-1].strip()
        if not isinstance(value, self._type):
            raise TypeError('Wrong Type')
        elif not value.upper() in self.grades:
            raise ValueError("Invalid grade value")


class ExtendedLetterGradeScheme(LetterGradeScheme):

    __metaclass__ = MetaGradeBookObject

    default_grades = (u'A+', u'A', u'A-',
                      u'B+', u'B', u'B-',
                      u'C+', u'C', u'C-',
                      u'D', u'D', u'F')

    default_ranges = ((90, 100), (86, 89), (80, 85),
                      (77, 79), (73, 76), (70, 72),
                      (67, 69), (63, 66), (60, 62),
                      (57, 59), (50, 56), (0, 49))


@interface.implementer(ILetterNumericGradeScheme)
class LetterNumericGradeScheme(LetterGradeScheme):

    __metaclass__ = MetaGradeBookObject

    def toDisplayableGrade(self, grade):
        value = getattr(grade, 'RawValue', grade)
        letter_grade = LetterGradeScheme.fromCorrectness(self, grade)
        numeric_grade = int(value * 100)
        if letter_grade is not None:
            return u"%s %s" % (letter_grade, numeric_grade)
        return numeric_grade


@WithRepr
@EqHash('min', 'max')
@interface.implementer(INumericGradeScheme, IContentTypeAware)
class NumericGradeScheme(SchemaConfigured):

    __metaclass__ = MetaGradeBookObject
    createDirectFieldProperties(INumericGradeScheme)

    _type = numbers.Number

    def fromUnicode(self, value):
        if value and value.endswith('-'):
            value = value[:-1].strip()
        value = float(value)
        self.validate(value)
        return value

    def validate(self, value):
        if not isinstance(value, self._type):
            raise TypeError('Wrong Type')
        elif value < self.min or value > self.max:
            raise ValueError("Invalid grade value")

    def toCorrectness(self, value):
        result = (value - self.min) / float(self.max - self.min)
        return result if result > 0 else 0.0

    def fromCorrectness(self, grade):
        value = getattr(grade, 'RawValue', grade)
        value = (min(max(0, value), 1))
        result = value * (self.max - self.min) + self.min
        result = round(result, 2)
        return result

    def toDisplayableGrade(self, grade):
        return self.fromCorrectness(grade)


@interface.implementer(INumericGradeScheme)
def _default_numeric_grade_scheme():
    result = NumericGradeScheme(min=0.0, max=100.0)
    return result


@interface.implementer(IIntegerGradeScheme, IContentTypeAware)
class IntegerGradeScheme(NumericGradeScheme):

    __metaclass__ = MetaGradeBookObject
    createDirectFieldProperties(IIntegerGradeScheme)

    _type = (int, long)

    def fromUnicode(self, value):
        if value and value.endswith('-'):
            value = value[:-1].strip()
        value = int(value)
        self.validate(value)
        return value

    def fromCorrectness(self, grade):
        value = getattr(grade, 'RawValue', grade)
        value = (min(max(0, value), 1))
        result = super(IntegerGradeScheme, self).fromCorrectness(value)
        result = int(round(result))
        return result


@interface.implementer(IIntegerGradeScheme)
def _default_integer_grade_scheme():
    result = IntegerGradeScheme(min=0, max=100)
    return result


@WithRepr
@interface.implementer(IBooleanGradeScheme, IContentTypeAware)
class BooleanGradeScheme(SchemaConfigured):

    __metaclass__ = MetaGradeBookObject
    createDirectFieldProperties(IBooleanGradeScheme)

    _type = bool

    true_values = TRUE_VALUES
    false_values = FALSE_VALUES

    @classmethod
    def fromUnicode(cls, value):
        if value and value.endswith('-'):
            value = value[:-1].strip()
        if value.lower() in cls.true_values:
            value = True
        elif value.lower() in cls.false_values:
            value = False
        cls.validate(value)
        return value

    @classmethod
    def validate(cls, value):
        if not isinstance(value, cls._type):
            raise TypeError('Wrong Type')

    def toCorrectness(self, value):
        result = 1.0 if value else 0.0
        return result

    def fromCorrectness(self, grade):
        value = getattr(grade, 'RawValue', grade)
        value = (min(max(0, value), 1))
        result = value >= 0.999
        return result

    def toDisplayableGrade(self, grade):
        return self.fromCorrectness(grade)

    def __eq__(self, other):
        return self is other or IBooleanGradeScheme.providedBy(other)

    def __hash__(self):
        xhash = 47
        xhash ^= hash(self.mimeType)
        return xhash


@WithRepr
@interface.implementer(ITotalPointsGradeScheme, IContentTypeAware)
class TotalPointsGradeScheme(SchemaConfigured):

    __metaclass__ = MetaGradeBookObject
    createDirectFieldProperties(ITotalPointsGradeScheme)

    _type = numbers.Number

    @classmethod
    def validate(cls, value):
        if not isinstance(value, cls._type):
            raise TypeError('Wrong Type')
        elif value < 0:
            raise ValueError("Grade cannot be less than 0")

    @classmethod
    def fromUnicode(cls, value):
        if value and value.endswith('-'):
            value = value[:-1].strip()
        value = float(value)
        cls.validate(value)
        return value

    def toDisplayableGrade(self, grade):
        return self.fromCorrectness(grade)

    def fromCorrectness(self, grade):
        result = getattr(grade, 'PointsEarned', grade)
        # Ensure that we never have a negative grade.
        if result and result <= 0:
            result = 0
        return result

    def toCorrectness(self, grade):
        # TODO: What do we need to do here??
        pass

    def __eq__(self, other):
        return self is other or ITotalPointsGradeScheme.providedBy(other)

    def __hash__(self):
        xhash = 47
        xhash ^= hash(self.mimeType)
        return xhash
