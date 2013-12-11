#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.assessment import interfaces as asm_interfaces

from . import gradebook
from . import interfaces as grade_interfaces

def _assignment_comparator(a, b):
    a_e = a.available_for_submission_ending
    b_e = b.available_for_submission_ending
    if a_e and b_e:
        return -1 if a_e < b_e else 1

    a_b = a.available_for_submission_beginning
    b_b = b.available_for_submission_beginning
    if a_b and b_b:
        return -1 if a_e < b_e else 1

    return 0

def create_assignments_entries(course):
    # get assignments
    assignments = []
    content_package = getattr(course, 'legacy_content_package', None)
    def _recur(unit):
        items = asm_interfaces.IQAssessmentItemContainer(unit, ())
        for item in items:
            if asm_interfaces.IQAssignment.providedBy(item):
                assignments.append(item)
        for child in unit.children:
            _recur(child)
    if content_package is not None:
        _recur(content_package)

    if not assignments:  # should not happen
        return 0

    weight = 1.0 / float(len(assignments))  # same weight

    # sort
    assignments = sorted(assignments, cmp=_assignment_comparator)

    # get gradebook from course
    book = grade_interfaces.IGradeBook(course)

    # create part
    part_name = 'Assignments'
    part = gradebook.GradeBookPart()
    part.displayName = part.Name = part_name
    part.order = 1
    part.weight = 1.0
    book[part_name] = part

    for idx, a in enumerate(assignments):
        n = idx + 1
        name = 'assignment%s' % n
        display = 'Assignment %s' % n
        entry = gradebook.GradeBookEntry(
                            Name=name, displayName=display, weight=weight, order=n,
                            assignmentId=getattr(a, 'NTIID', getattr(a, 'ntiid', None)))

        part[name] = entry

    return len(assignments)

