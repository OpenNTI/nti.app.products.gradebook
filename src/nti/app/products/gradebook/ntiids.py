#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses import get_courses_catalog

from nti.contenttypes.courses.index import IX_NAME
from nti.contenttypes.courses.index import IX_SITE

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.interfaces import INTIIDResolver

from nti.ntiids.ntiids import get_specific

from nti.site.site import get_component_hierarchy_names

logger = __import__('logging').getLogger(__name__)


def get_course(key):
    catalog = get_courses_catalog()
    intids = component.getUtility(IIntIds)
    # XXX: Resolve according to hierarchy
    for site in get_component_hierarchy_names():
        query = {
            IX_NAME: {'any_of': key},
            IX_SITE: {'any_of': (site,)}
        }
        for doc_id in catalog.apply(query) or ():
            course = intids.queryObject(doc_id)
            if ICourseInstance.providedBy(course):
                return course
    return None


@interface.implementer(INTIIDResolver)
class _GradeBookResolver(object):

    def resolve(self, key):
        name = get_specific(key)
        course = get_course(name)
        return IGradeBook(course, None)


@interface.implementer(INTIIDResolver)
class _GradeBookPartResolver(object):

    def resolve(self, key):
        specific = get_specific(key)
        try:
            course, part = specific.split('.')[-2]
            course = get_course(course)
            gradebook = IGradeBook(course, None)
            if gradebook:
                return gradebook[part]
        except ValueError:
            logger.error("'%s' invalid gradebook part NTIID", key)
        except KeyError:
            logger.error("Cannot find gradebook part using '%s'", key)
        return None


@interface.implementer(INTIIDResolver)
class _GradeBookEntryResolver(object):

    def resolve(self, key):
        specific = get_specific(key)
        try:
            course, part, entry = specific.split('.')[-3]
            course = get_course(course)
            gradebook = IGradeBook(course, None)
            if gradebook and part in gradebook:
                parts = gradebook[part]
                return parts[entry]
        except ValueError:
            logger.error("'%s' invalid gradebook entry NTIID", key)
        except KeyError:
            logger.error("Cannot find gradebook entry using '%s'", key)
        return None
