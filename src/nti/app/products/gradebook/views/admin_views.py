#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.dataserver import authorization as nauth

from ..interfaces import IGradeScheme
from ..interfaces import IGradeBookEntry

@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='PUT',
             context=IGradeBookEntry,
             permission=nauth.ACT_UPDATE)
class SetGradeSchemeView(AbstractAuthenticatedView,
                         ModeledContentEditRequestUtilsMixin,
                         ModeledContentUploadRequestUtilsMixin):
    
    content_predicate = IGradeScheme.providedBy

    def _do_call(self):
        theObject = self.request.context
        theObject.creator = self.getRemoteUser()

        self._check_object_exists(theObject)
        self._check_object_unmodified_since(theObject)

        externalValue = self.readInput()
        theObject.GradeScheme = externalValue

        return theObject
