#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.container.interfaces import INameChooser

from nti.app.assessment.common.evaluations import assignment_comparator
from nti.app.assessment.common.evaluations import get_course_assignments
from nti.app.assessment.common.evaluations import get_all_course_assignments

from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import NoSubmitGradeBookPart

from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

logger = __import__('logging').getLogger(__name__)


# BWC
_assignment_comparator = assignment_comparator
get_course_assignments = get_course_assignments


def create_assignment_part(course, part_name, _book=None):
    book = _book if _book is not None else IGradeBook(course)
    if part_name not in book:
        if part_name == NO_SUBMIT_PART_NAME:
            factory = NoSubmitGradeBookPart
        else:
            factory = GradeBookPart

        part = factory(displayName=part_name,
                       order=1)  # Order makes very little sense here...
        # pylint: disable=too-many-function-args
        book[INameChooser(book).chooseName(part_name, part)] = part
    return book[part_name]
get_or_create_assignment_part = create_assignment_part


def create_assignment_entry(course, assignment, displayName,
                            order=1, _book=None, reset_entry_location=False):
    book = _book if _book is not None else IGradeBook(course)

    assignmentId = assignment.__name__

    entry = book.getColumnForAssignmentId(assignmentId)
    if entry is None:
        part = get_or_create_assignment_part(course,
                                             assignment.category_name)
        # Hmm, maybe we should just ask it to create the entry
        part.validateAssignment(assignment)
        entry = part.entryFactory(displayName=displayName,
                                  order=order,
                                  AssignmentId=assignmentId)
        # pylint: disable=too-many-function-args
        part[INameChooser(part).chooseName(displayName, entry)] = entry
    elif entry.displayName != displayName:
        entry.displayName = displayName

    if reset_entry_location:
        entry = book.getColumnForAssignmentId(assignmentId)
        part = get_or_create_assignment_part(course,
                                             assignment.category_name)
        part._delitemf(entry.__name__, event=False)
        part[INameChooser(part).chooseName(displayName, entry)] = entry

    return entry
get_or_create_assignment_entry = create_assignment_entry


def synchronize_gradebook(context, reset_entry_location=False):
    """
    Makes the gradebook for the course match the assignments for the course.

    New assignments are added to a part matching their category. If an assignment
    exists in the book but not the course assignments, and there are
    no recorded grades, it is removed.
    """
    course = ICourseInstance(context, None)
    if course is None:
        return
    catalog_entry = ICourseCatalogEntry(course, None)
    course_ntiid = getattr(catalog_entry, 'ntiid', '')
    logger.info("Syncing gradebook for %s", course_ntiid)

    assignment_ids = set()
    book = IGradeBook(course)
    assignments = get_all_course_assignments(course)

    category_map = {}
    # pylint: disable=too-many-function-args
    for part in book.values():
        for entry in part.values():
            category_map[entry.assignmentId] = part.__name__

    # Warning !!! What if an assignment changes parts (category_name)?
    # We'll need to move them
    for idx, assignment in enumerate(assignments):
        ordinal = idx + 1
        assignment_ids.add(assignment.__name__)
        if assignment.title:
            displayName = assignment.title
        else:
            displayName = u'Assignment %s' % ordinal
        create_assignment_entry(course, assignment, displayName,
                                ordinal, book, reset_entry_location=reset_entry_location)

    # Now drop entries that don't correspond to existing assignments
    # and that don't have grades
    for part in tuple(book.values()):
        for entry in tuple(part.values()):
            if entry.assignmentId not in assignment_ids and len(entry) == 0:
                try:
                    del part[entry.__name__]
                    logger.info('Removed %s from gradebook for %s',
                                entry.assignmentId,
                                course_ntiid)
                except TypeError:
                    logger.warning("Failed to remove part %s",
                                   part, exc_info=True)

        if not part:
            del book[part.__name__]

    # Now check consistency due to the above fixme. Until we get it fixed,
    # don't let it happen
    entry_aids = set()
    for part in book.values():
        for entry in part.values():
            if entry.AssignmentId in entry_aids:
                raise ValueError("An assignment changed categories. Not currently allowed.")
                # use svn history to figure out what it used to be and change
                # it back
            entry_aids.add(entry.AssignmentId)

    result = len(assignments)
    return result
