#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

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
