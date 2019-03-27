#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope.cachedescriptors.property import Lazy

from nti.app.assessment import VIEW_RESET_EVALUATION

from nti.app.assessment.views.reset_views import UserHistoryItemResetView

from nti.app.products.gradebook.interfaces import IGrade

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import StandardExternalFields
from nti.contenttypes.courses.interfaces import ICourseInstance

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(context=IGrade)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_RESET_EVALUATION,
               request_method='POST',
               permission=ACT_READ)
class GradeResetView(UserHistoryItemResetView):
    """
    XXX: Now that we no longer have placeholder submissions, we may have
    grades without submissions or submissions without grades. To help retain
    BWC, we decorate and have a grade specific view to reset a user's
    submission history (and grades).
    """

    def _delete_contained_data(self, course, unused_assignment_ntiid):
        # This param is actually the context.__name__ in super
        assignment_ntiid = self.context.AssignmentId
        result = super(GradeResetView, self)._delete_contained_data(course,
                                                                    assignment_ntiid)
        # Must clear the grade container here since we may not have submissions
        # In the assessment container version of this, subscribers take care
        # of grade entries once the history item container is reset.
        grade_container = self.context.__parent__
        grade_container.reset()
        return result

    @Lazy
    def course(self):
        return ICourseInstance(self.context, None)
