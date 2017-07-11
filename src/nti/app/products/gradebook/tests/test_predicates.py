#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from nti.assessment.submission import QuestionSetSubmission
from nti.assessment.submission import AssignmentSubmission

from nti.app.products.gradebook import predicates

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.externalization.externalization import to_external_object

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

COURSE_NTIID = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'


class TestPredictes(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    assignment_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1"
    question_set_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:ASMT1_ichigo"

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_predicates(self):

        extra_env = self.testapp.extra_environ or {}
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
        submission = AssignmentSubmission(assignmentId=self.assignment_id, 
										  parts=(qs_submission,))
        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (self.assignment_id, COURSE_NTIID)

        ext_obj = to_external_object(submission)
        del ext_obj['Class']
        assert_that(ext_obj, 
					has_entry('MimeType', 'application/vnd.nextthought.assessment.assignmentsubmission'))

        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        self.testapp.post_json(submit_href, ext_obj, status=201)

        with mock_dataserver.mock_db_trans(self.ds):
            user = self._get_user('sjohnson@nextthought.com')
            predicate = predicates._GradePrincipalObjects(user)
            grades = list(predicate.iter_objects())
            assert_that(grades, has_length(1))

            predicate = predicates._GradeBookPrincipalObjects()
            objects = list(predicate.iter_objects())
            assert_that(objects, greater_than(70))
