#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import logging

from zope import component
from zope.security.interfaces import IPrincipal
from zope.container.interfaces import INameChooser

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

from ..grades import PersistentGrade
from ..interfaces import NO_SUBMIT_PART_NAME
from ..assignments import create_assignment_part

VIEW_CURRENT_GRADE = 'CurrentGrade'

def find_grading_policy_for_course(context):
    course = ICourseInstance(context, None)
    if course is None:
        return None

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
        
    # We need to actually be registering these as annotations
    policy = ICourseGradingPolicy(course, None)
    return policy

def calculate_grades(context, usernames=(), grade_scheme=None, 
                     entry_name=None, verbose=False):
    
    if verbose:
        logger.setLevel(logging.DEBUG)

    result = {}
    course = ICourseInstance(context)
    policy = find_grading_policy_for_course(course)
    if policy is None:
        raise ValueError("Course does not have grading policy")
       
    if entry_name:
        part = create_assignment_part(course, NO_SUBMIT_PART_NAME)
        entry = part.getEntryByAssignment(entry_name)
        if entry is None:
            order = len(part) + 1
            entry = part.entryFactory(displayName=entry_name, 
                                      order=order,
                                      AssignmentId=entry_name)
            part[INameChooser(part).chooseName(entry_name, entry)] = entry
    else:
        entry = None
        
    for record in ICourseEnrollments(course).iter_enrollments():
        principal = IPrincipal(record.Principal, None)
        if principal is None:
            # ignore dup enrollment
            continue

        username = principal.id.lower()
        if usernames and username not in usernames:
            continue
        
        # grade correctness
        value = correctness = policy.grade(principal)
        
        # if there is a grade scheme convert value
        if grade_scheme is not None:
            value = grade_scheme.fromCorrectness(correctness)
        
        grade = PersistentGrade(value=value)
        grade.username = username
        result[username] = grade
        
        # if entry is available save it
        if entry is not None:
            entry[username] = grade
    return result
