#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook externalization

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.app.assessment import interfaces as appa_interfaces

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import interfaces as nti_interfaces

from nti.externalization import externalization
from nti.externalization import interfaces as ext_interfaces
from nti.externalization.singleton import SingletonDecorator
from nti.externalization.datastructures import LocatedExternalDict
from nti.externalization.autopackage import AutoPackageSearchingScopedInterfaceObjectIO

from . import interfaces as grade_interfaces

CLASS = ext_interfaces.StandardExternalFields.CLASS
MIMETYPE = ext_interfaces.StandardExternalFields.MIMETYPE

@interface.implementer(ext_interfaces.IExternalObject)
@component.adapter(grade_interfaces.IBooleanGradeScheme)
class BooleanGradeSchemeExternalizer(object):

	__slots__ = ('value',)

	def __init__(self, value):
		self.value = value

	def toExternalObject(self):
		return True if self.value else False

@interface.implementer(ext_interfaces.IExternalObject)
@component.adapter(grade_interfaces.IGrades)
class GradesExternalizer(object):

	__slots__ = ('grades',)

	def __init__(self, grades):
		self.grades = grades

	def toExternalObject(self):
		result = LocatedExternalDict({CLASS:'Grades', MIMETYPE:self.grades.mimeType})
		items = result['Items'] = {}
		for username, grades in self.grades.items():
			lst = items[username] = []
			for g in grades:
				ext = externalization.to_external_object(g)
				lst.append(ext)
		return result

@interface.implementer(ext_interfaces.IInternalObjectIO)
class GradesObjectIO(AutoPackageSearchingScopedInterfaceObjectIO):

	@classmethod
	def _ap_enumerate_externalizable_root_interfaces(cls, grade_interfaces):
		return (grade_interfaces.IGradeBookEntry, grade_interfaces.IGradeBookPart,
				grade_interfaces.IGradeBook, grade_interfaces.IGrade,
				grade_interfaces.IGrades)

	@classmethod
	def _ap_enumerate_module_names(cls):
		return ('gradebook', 'grades')

GradesObjectIO.__class_init__()


@component.adapter(appa_interfaces.IUsersCourseAssignmentHistoryItem)
@interface.implementer(ext_interfaces.IExternalObjectDecorator)
class UsersCourseAssignmentHistoryItemDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		entry = grade_interfaces.IGradeBookEntry(original, None)
		if entry is not None:
			course = ICourseInstance(original)
			user = nti_interfaces.IUser(original)
			course_grades = grade_interfaces.IGrades(course)
			grade = course_grades.find_grade(entry.NTIID, user.username)
			if grade is None:
				external['Grade'] = externalization.to_external_object(grade)
