#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generations for managing gradebook.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.intid.interfaces import IIntIds

from zope.generations.generations import SchemaManager

from nti.app.products.gradebook.index import install_grade_catalog

generation = 11

logger = __import__('logging').getLogger(__name__)


class _GradeBookSchemaManager(SchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """

    def __init__(self):
        super(_GradeBookSchemaManager, self).__init__(
            generation=generation,
            minimum_generation=generation,
            package_name='nti.app.products.gradebook.generations')


def evolve(context):
    conn = context.connection
    dataserver_folder = conn.root()['nti.dataserver']
    lsm = dataserver_folder.getSiteManager()
    intids = lsm.getUtility(IIntIds)
    install_grade_catalog(dataserver_folder, intids)
    return context
