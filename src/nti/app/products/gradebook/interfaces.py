#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import interface
from zope.interface.interface import taggedValue

from zope.container.constraints import contains
from zope.container.interfaces import IContainer
from zope.container.interfaces import IContained
from zope.container.constraints import containers

from zope.security.permission import Permission

from nti.app.client_preferences.interfaces import TAG_EXTERNAL_PREFERENCE_GROUP

from nti.dataserver.interfaces import ILastModified
from nti.dataserver.interfaces import IShouldHaveTraversablePath
from nti.dataserver.interfaces import IUsernameSubstitutionPolicy

from nti.ntiids.schema import ValidNTIID

from nti.schema.field import Int
from nti.schema.field import Bool
from nti.schema.field import Date
from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import Variant
from nti.schema.field import TextLine
from nti.schema.field import ListOrTuple
from nti.schema.field import ValidTextLine

ACT_VIEW_GRADES = Permission('nti.actions.gradebook.view_grades')

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
	min = Number(title="min value", default=0.0, min=0.0)
	max = Number(title="max value", default=100.0)

class IIntegerGradeScheme(INumericGradeScheme):
	min = Int(title="min value", default=0, min=0)
	max = Int(title="max value", default=100)

class ILetterGradeScheme(IGradeScheme):

	grades = ListOrTuple(TextLine(title="the letter",
								  min_length=1,
								  max_length=1),
						  unique=True,
						  min_length=1)

	ranges = ListOrTuple(ListOrTuple(Number(title="the range value", min=0),
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

class IGradeBookEntry(IContainer,
					  IContained,
					  IShouldHaveTraversablePath):
	"""
	A 'column' in the gradebook. This contains a grade entry
	for each student in the course once they've completed
	the corresponding assignment.
	"""

	containers(str('.IGradeBookPart'))
	contains(str('.IGrade'))
	__parent__.required = False

	Name = ValidTextLine(title="entry name", required=False)

	GradeScheme = Object(IGradeScheme, description="A :class:`.IGradeScheme`",
						 title="The grade scheme", required=False)

	displayName = ValidTextLine(title="Part name", required=False)

	AssignmentId = ValidTextLine(title="assignment id", required=True)

#	weight = schema.Float(title="The relative weight of this entry, from 0 to 1",
#						  min=0.0,
#						  max=1.0,
#						  default=1.0,
#						  required=False)

	order = Int(title="The entry order", min=1)

	DueDate = Date(title="The date on which the assignment is due", required=False,
				   readonly=True)

	Items = Dict(title="For externalization only, a copy of the {username: grade} contents}",
				 description="For expedience and while while we expect these to be relatively small, we inline them",
				 readonly=True)

class ISubmittedAssignmentHistoryBase(IShouldHaveTraversablePath):
	"""
	Something that can get all the assignment histories
	that have been submitted. Typically this will be
	registered as an adapter for :class:`.IGradeBookEntry`,
	in which case the scope of what it returns is limited to that
	entry's assignment.
	"""

	def __iter__():
		"""
		Iterating across this object iterates across (username, historyitem)
		pairs, like iterating across a dictionary.
		"""

	def __len__():
		"""
		The length of this item is how many submitted assignments
		there have been (and hence how many non-null items can
		be expected).
		"""

	def items(usernames=None, placeholder=None):
		"""
		Return an iterator over the items (username, historyitem)
		that make up this object. This is just like iterating over
		this object normally, except the option of filtering.

		:keyword usernames: If given, an iterable of usernames.
			Only usernames that are in this iterable are returned.
			Furthermore, the items are returned in the same order
			as the usernames in the iterable. Note that if the username
			doesn't exist, nothing is returned for that entry
			unless `placeholder` is also provided.
		:keyword placeholder: If given (even if given as None)
			then all users in `usernames` will be returned; those
			that have not submitted will be returned with this placeholder
			value. This only makes sense if usernames is given.
		"""

class ISubmittedAssignmentHistory(ISubmittedAssignmentHistoryBase):
	"Returns full assignment history items."


class ISubmittedAssignmentHistorySummaries(ISubmittedAssignmentHistoryBase):
	"Returns summary assignment history items"


class IGradeBookPart(IContainer,
					 IContained,
					 IShouldHaveTraversablePath):
	"""
	A Section of a grade book e.g. Quizzes, Exams, etc..
	"""

	containers(str('.IGradeBook'))
	contains(IGradeBookEntry)
	__parent__.required = False

	entryFactory = interface.Attribute("A callable used to create the entries that go in this part.")
	entryFactory.setTaggedValue('_ext_excluded_out', True)

	def validateAssignment(assignment):
		"Check that the given assignment is valid to go in this part."

	Name = ValidTextLine(title="Part name", required=False)
	displayName = ValidTextLine(title="Part name", required=False)
	gradeScheme = Object(IGradeScheme, description="A :class:`.IGradeScheme`",
						 title="The grade scheme for this part", required=False)

	order = Int(title="The part order", min=1)

	#TotalEntryWeight = schema.Float(title="Entry weight sum", readonly=True)

	Items = Dict(title="For externalization only, a copy of the {assignmentId: GradeBookEntry} contents}",
						description="For expedience and while while we expect these to be relatively small, we inline them",
						readonly=True)

	def get_entry_by_assignment(assignmentId):
		"""
		return the :IGradeBookEntry associated with the specified assignmentId
		"""

	def remove_user(username):
		"""
		remove the grades for the specififed user from this part
		"""
	
	def has_grades(username):
		"""
		returns true if there are grades for the specififed user in this part
		"""
	
	def iter_grades(username):
		"""
		returns an iterator for the specififed user's grades
		"""

#: This is a special category name for assignments that are
#: only ever given grades by the professor; no submission
#: of them is possible. Examples include midterm and final
#: grades
NO_SUBMIT_PART_NAME = 'no_submit'

# special final grade name
FINAL_GRADE_NAME = 'Final Grade'

class IGradeBook(IContainer,
				 IContained,
				 IShouldHaveTraversablePath):
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

	def remove_user(username):
		"""
		remove the grades for the specififed user from this grade book
		"""
	
	def has_grades(username):
		"""
		returns true if there are grades for the specififed user in this grade book
		"""
	
	def iter_grades(username):
		"""
		returns an iterator for the specififed user's grades
		"""
		
	Items = Dict(title="For externalization only, a copy of the {category name: GradeBookPart} contents}",
				 description="For expedience and while while we expect these to be relatively small, we inline them",
				 readonly=True)

def _grade_property():
	return Variant((Number(title="Number grade"),
					Bool(title="Boolean grade"),
					ValidTextLine(title="String grade")),
				   title="The grade",
				   required=False)

class IGrade(IContained,
			 ILastModified,
			 IShouldHaveTraversablePath):
	"""
	A single grade for a single user.

	Note that due to the large number of these, implementations
	should NOT typically be persistent; updating consists
	of replacing the pickle entirely.
	"""

	containers(IGradeBookEntry)
	__parent__.required = False

	Username = ValidTextLine(title="Username",
							 description="Because grades are stored by username, this is "
							 "equivalent to __name__",
							 required=True)

	# NTIID = ValidNTIID(title="Grade entry ntiid", required=True)
	AssignmentId = ValidNTIID(title="The assignment this is for",
							  description="This comes from the entry containing it.",
							  required=False)

	value = _grade_property()

	AutoGrade = _grade_property()
	AutoGradeMax = _grade_property()

class IExcusedGrade(IGrade):
	"""
	Marker interface for an Excused grade
	"""
IExcusedGrade.setTaggedValue('_ext_is_marker_interface', True)

class IPendingAssessmentAutoGradePolicy(interface.Interface):
	"""
	An object that can interpret the results of the
	auto-assessed parts of an assignment and produce
	an output 'grade' value.
	"""

	def autograde(item):
		"""
		Given the :class:`nti.assessment.interfaces.IQAssignmentSubmissionPendingAssessment`,
		examine the parts and produce a tuple usable as the auto-graded value:
		(AutoGrade, AutoGradeMax)

		Return None if no autograding is possible.
		"""

IUsernameSortSubstitutionPolicy = IUsernameSubstitutionPolicy # alias

class IGradebookSettings(interface.Interface):
	"""
	The root of the settings tree for gradebook
	"""
	taggedValue(TAG_EXTERNAL_PREFERENCE_GROUP, 'write')

	hide_avatars = Bool(title="Enable/disable showing avatars in the gradebook",
						description="Enable/disable showing avatars in the gradebook",
						default=False)
