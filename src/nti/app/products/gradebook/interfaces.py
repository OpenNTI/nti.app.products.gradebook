#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface
from zope.interface.common import mapping
from zope.container.constraints import contains, containers
from zope.container.interfaces import IContainer, IContained

from nti.utils import schema
from nti.ntiids.schema import ValidNTIID

# ## NTIID values

NTIID_TYPE_GRADE_BOOK = 'gradebook'

NTIID_TYPE_GRADE_BOOK_PART = 'gradebookpart'

NTIID_TYPE_GRADE_BOOK_ENTRY = 'gradebookentry'

class IGradeScheme(interface.Interface):

	def fromUnicode(value):
		pass

	def validate(value):
		pass

	def toCorrectness(grade):
		"""
		return the relative correctness of the grade
		"""

	def fromCorrectness(value):
		"""
		return a grade from the specified correctness value
		"""

class INumericGradeScheme(IGradeScheme):
	min = schema.Number(title="min value", default=0.0, min=0.0)
	max = schema.Number(title="max value", default=100.0)

class IIntegerGradeScheme(INumericGradeScheme):
	min = schema.Int(title="min value", default=0, min=0)
	max = schema.Int(title="max value", default=100)

class ILetterGradeScheme(IGradeScheme):

	grades = schema.ListOrTuple(schema.TextLine(title="the letter",
										  min_length=1,
										  max_length=1),
						  unique=True,
						  min_length=1)

	ranges = schema.ListOrTuple(schema.ListOrTuple(schema.Number(title="the range value", min=0),
												   min_length=2,
												   max_length=2),
						  unique=True,
						  min_length=1)

	def toLetter(value):
		"""
		return the letter grade for the specified value
		"""

	def toNumber(letter):
		"""
		return the number grade for the specified letter
		"""

class IBooleanGradeScheme(IGradeScheme):
	pass

class IGradeBookEntry(IContainer, IContained):
	"""
	A 'column' in the gradebook. This contains a grade entry
	for each student in the course once they've completed
	the corresponding assignment.
	"""

	containers(str('.IGradeBookPart'))
	contains(str('.IGrade'))
	__parent__.required = False

	Name = schema.ValidTextLine(title="entry name", required=False)

	GradeScheme = schema.Object(IGradeScheme, description="A :class:`.IGradeScheme`",
								  title="The grade scheme", required=False)

	displayName = schema.ValidTextLine(title="Part name",
									   required=False)
	AssignmentId = schema.ValidTextLine(title="assignment id",
										required=True)

#	weight = schema.Float(title="The relative weight of this entry, from 0 to 1",
#						  min=0.0,
#						  max=1.0,
#						  default=1.0)
	order = schema.Int(title="The entry order", min=1)
	DueDate = schema.Date(title="The date on which the assignment is due", required=False,
						  readonly=True)

class IGradeBookPart(IContainer, IContained):
	"""
	A Section of a grade book e.g. Quizzes, Exams, etc..
	"""

	containers(str('.IGradeBook'))
	contains(IGradeBookEntry)
	__parent__.required = False

	Name = schema.ValidTextLine(title="Part name", required=False)
	displayName = schema.ValidTextLine(title="Part name", required=False)
	gradeScheme = schema.Object(IGradeScheme, description="A :class:`.IGradeScheme`",
								  title="The grade scheme for this part", required=False)
#	weight = schema.Float(title="The relative weight of this part, from 0 to 1",
#						  min=0.0,
#						  max=1.0,
#						  default=1.0,
#						  required=True)
	order = schema.Int(title="The part order", min=1)

	#TotalEntryWeight = schema.Float(title="Entry weight sum", readonly=True)

	def get_entry_by_assignment(assignmentId):
		"""
		return the :IGradeBookEntry associated with the specified assignmentId
		"""

class IGradeBook(IContainer, IContained):
	"""
	Grade book definition
	"""
	contains(IGradeBookPart)

	#TotalPartWeight = schema.Float(title="Part weight sum", readonly=True)

	def getColumnForAssignmentId(assignmentId):
		"""
		return the :IGradeBookEntry associated with the specified assignmentId
		"""


	def get_entry_by_ntiid(ntiid):
		"""
		return the :IGradeBookEntry associated with the specified ntiid
		"""

class IGrade(IContained):
	"""
	A single grade for a single user.

	Note that due to the large number of these, implementations
	should NOT typically be persistent; updating consists
	of replacing the pickle entirely.
	"""

	containers(IGradeBookEntry)

	Username = schema.ValidTextLine(title="Username",
									description="""Because grades are stored by username, this is
									equivalent to __name__""",
									required=True)
	#NTIID = ValidNTIID(title="Grade entry ntiid", required=True)
	AssignmentId = ValidNTIID(title="The assignment this is for",
							  description="This comes from the entry containing it.",
							  required=False)
	# XXX: This may change depending on input from OU
	value = schema.Variant(
				(schema.Number(title="Number grade"),
				 schema.Bool(title='Boolean grade'),
				 schema.ValidTextLine(title='String grade')),
		title="The grade", required=False)

	# Storing or returning the calculated 'AutoGrade'
	# turns out not to be useful in the current designs: due to the mix
	# of auto-assessable and non-auto-assessable parts, the instructor
	# needs to review each individual part.
	#AutoGrade = schema.Float(title="Auto grade", min=0.0, required=False, readonly=True)


#class IGrades(interface.Interface):
	# """
	# User grades
	# """

	# def get_grades(username):
	# 	pass

	# def add_grade(grade):
	# 	pass

	# def remove_grade(grade, username=None):
	# 	pass

	# def remove_grades(ntiid):
	# 	pass

	# def clear(username):
	# 	pass

	# def clearAll():
	# 	pass
