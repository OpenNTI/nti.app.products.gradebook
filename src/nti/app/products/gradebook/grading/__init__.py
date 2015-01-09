#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope.security.interfaces import IPrincipal
from zope.container.interfaces import INameChooser

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

from ..grades import Grade
from ..interfaces import NO_SUBMIT_PART_NAME
from ..assignments import create_assignment_part

def find_grading_policy_for_course(course):
    # We need to actually be registering these as annotations
    policy = ICourseGradingPolicy(course, None)
    if policy is not None:
        return policy

    registry = component
    try:
        # Courses may be ISites 
        registry = course.getSiteManager()
        names = ('',)
    except LookupError:
        # try content pacakges
        names = [x.ntiid for x in course.ContentPackageBundle.ContentPackages]
        # try catalog entry
        cat_entry = ICourseCatalogEntry(course, None)
        if cat_entry:
            names.append(cat_entry.ntiid)
            names.append(cat_entry.ProviderUniqueID)

    for name in names:
        try:
            return registry.getUtility(ICourseGradingPolicy, name=name)
        except LookupError:
            pass
    return None

def calculate_grades(course, grade_scheme, entry_name='Current_Grade'):
    result = {}
    
    policy = find_grading_policy_for_course(course)
    if policy is None:
        raise ValueError("Course does not have grading policy")
       
    part = create_assignment_part(course, NO_SUBMIT_PART_NAME)
    entry = part.getEntryByAssignment(entry_name)
    if entry is None:
        order = len(part) + 1
        entry = part.entryFactory(displayName=entry_name, 
                                  order=order,
                                  AssignmentId=entry_name)
        part[INameChooser(part).chooseName(entry_name, entry)] = entry
        
    for record in ICourseEnrollments(course).iter_enrollments():
        principal = record.principal
        username = IPrincipal(principal).id
        
        correctness = policy.grade(principal)
        value = grade_scheme.fromCorrectness(correctness)
        
        grade = Grade(value=value)
        entry[username] = grade
        result[username] = grade
    return result
