#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import schema
from zope import interface
from zope.interface.common import mapping
from zope.container.constraints import contains, containers
from zope.container.interfaces import IContainer, IContained

from dolmen.builtins import INumeric, IString, IBoolean

from nti.utils import schema as dmschema

# ## NTIID values

NTIID_TYPE_GRADE_BOOK = 'gradebook'

NTIID_TYPE_GRADE_BOOK_PART = 'gradebookpart'

NTIID_TYPE_GRADE_BOOK_ENTRY = 'gradebookentry'

class ICloneable(interface.Interface):

	def clone():
		"""
		clone this object
		"""

class IGradeBookEntry(IContained, ICloneable):

	containers(b'.IGradeBookPart')
	__parent__.required = False

	Name = dmschema.ValidTextLine(title="entry name", required=False)
	displayName = dmschema.ValidTextLine(title="Part name", required=False)
	assignmentId = dmschema.ValidTextLine(title="assignment id", required=False)
	maxGrade = schema.Int(title="The maximum grade that can be obtained",
						  min=0, max=100, required=False, default=100)
	weight = schema.Float(title="The relative weight of this entry, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0)
	order = schema.Int(title="The entry order", min=1)
	DueDate = schema.Date(title="The date on which the assignment is due", required=False,
						  readonly=True)
	
class IGradeBookPart(IContainer, IContained, ICloneable, mapping.IClonableMapping):
	"""
	A Section of a grade book e.g. Quizzes, Exams, etc..
	"""
	containers(b'.IGradeBook')
	contains(b'.IGradeBookEntry')
	__parent__.required = False

	Name = dmschema.ValidTextLine(title="Part name", required=False)
	displayName = dmschema.ValidTextLine(title="Part name", required=False)
	weight = schema.Float(title="The relative weight of this part, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0,
						  required=True)
	order = schema.Int(title="The part order", min=1)

	TotalEntryWeight = schema.Float(title="Entry weight sum", readonly=True)

	def get_entry_by_assignment(assignmentId):
		"""
		return the :IGradeBookEntry associated with the specified assignmentId
		"""

class IGradeBook(IContainer, IContained, ICloneable, mapping.IClonableMapping):
	"""
	Grade book definition
	"""
	contains(b'.IGradeBookPart')
	TotalPartWeight = schema.Float(title="Part weight sum", readonly=True)

	def get_entry_by_ntiid(ntiid):
		"""
		return the :IGradeBookEntry associated with the specified ntiid
		"""
		
	def get_entry_by_assignment(assignmentId):
		"""
		return the :IGradeBookEntry associated with the specified assignmentId
		"""

class IGradeScheme(interface.Interface):
	pass

class INumericGradeScheme(IGradeScheme, INumeric):
	pass

class IStringGradeScheme(IGradeScheme, IString):
	pass

class IBooleanGradeScheme(IGradeScheme, IBoolean):
	pass

class IGrade(IContained, ICloneable):
	"""
	Grade entry
	"""
	username = dmschema.ValidTextLine(title="Username", required=True)
	ntiid = dmschema.ValidTextLine(title="Grade entry ntiid", required=True)
	grade = schema.Object(IGradeScheme, title="The grade", required=False)

	AutoGrade = schema.Float(title="Auto grade", min=0.0, required=False, readonly=True)

	def copy(source):
		"""
		copy the data from the source object
		"""

class IGrades(mapping.IMapping, IContained):
	"""
	User grades
	"""
	
	def get_grades(username):
		pass

	def add_grade(grade):
		pass

	def remove_grade(grade, username=None):
		pass

	def remove_grades(ntiid):
		pass

	def clear(username):
		pass

	def clearAll():
		pass
