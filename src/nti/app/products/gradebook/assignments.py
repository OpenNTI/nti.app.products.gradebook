#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.container.interfaces import INameChooser

from nti.app.assessment.interfaces import ICourseAssignmentCatalog

from .interfaces import IGradeBook
from .interfaces import NO_SUBMIT_PART_NAME

from .gradebook import GradeBookPart
from .gradebook import NoSubmitGradeBookPart

def _assignment_comparator(a, b):
	a_end = a.available_for_submission_ending
	b_end = b.available_for_submission_ending
	if a_end and b_end:
		return -1 if a_end < b_end else 1

	a_begin = a.available_for_submission_beginning
	b_begin = b.available_for_submission_beginning
	if a_begin and b_begin:
		return -1 if a_begin < b_begin else 1

	return 0

def get_course_assignments(course, sort=True, reverse=False):
	assignments = list(ICourseAssignmentCatalog(course).iter_assignments())

	if sort:
		assignments = sorted(assignments, cmp=_assignment_comparator, reverse=reverse)
	return assignments

def create_assignment_part(course, part_name, _book=None):
	book = _book if _book is not None else IGradeBook(course)
	if part_name not in book:
		if part_name == NO_SUBMIT_PART_NAME:
			factory = NoSubmitGradeBookPart
		else:
			factory = GradeBookPart

		part = factory(displayName=part_name,
					   order=1) # Order makes very little sense here...

		book[INameChooser(book).chooseName(part_name, part)] = part
	return book[part_name]

get_create_assignment_part = create_assignment_part

def create_assignment_entry(course, assignment, displayName, order=1, _book=None):
	book = _book if _book is not None else IGradeBook(course)

	assignmentId = assignment.__name__

	entry = book.getColumnForAssignmentId(assignmentId)
	if entry is None:
		part = get_create_assignment_part(course, assignment.category_name)
		part.validateAssignment(assignment) # Hmm, maybe we should just ask it to create the entry
		entry = part.entryFactory(
							   displayName=displayName,
							   order=order,
							   AssignmentId=assignmentId)
		part[INameChooser(part).chooseName(displayName, entry)] = entry

	return entry
get_create_assignment_entry = create_assignment_entry

def synchronize_gradebook(course):
	"""
	Makes the gradebook for the course match the assignments for the course.

	New assignments are added to a part matching their category. If an assignment
	exists in the book but not the course assignments, and there are
	no recorded grades, it is removed.
	"""
	if course is None:
		return

	assignments = get_course_assignments(course)
	book = IGradeBook(course)

	assignment_ids = set()

	# FIXME: What if an assignment changes parts (category_name)?
	# We'll need to move them
	for idx, assignment in enumerate(assignments):
		ordinal = idx + 1
		if assignment.title:
			displayName = assignment.title
		else:
			displayName = 'Assignment %s' % ordinal
		create_assignment_entry(course, assignment, displayName, ordinal, book)
		assignment_ids.add( assignment.__name__ )

	# Now drop entries that don't correspond to existing assignments
	# and that don't have grades
	for part in book.values():
		for entry in part.values():
			if entry.assignmentId not in assignment_ids and len(entry) == 0:
				try:
					del part[entry.__name__]
				except TypeError:
					logger.warning("Failed to remove part %s", part, exc_info=True)

		if not part:
			del book[part.__name__]

	# Now check consistency due to the above fixme. Until we get it fixed,
	# don't let it happen
	entry_aids = set()
	for part in book.values():
		for entry in part.values():
			if entry.AssignmentId in entry_aids:
				raise ValueError("An assignment changed categories. Not currently allowed.")
				# use svn history to figure out what it used to be and change it back
			entry_aids.add(entry.AssignmentId)

	return len(assignments)
