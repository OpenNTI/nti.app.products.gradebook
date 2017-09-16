====================================
 Grading policy usage
====================================


Conceptual Documentation
========================

A course with autograded assignments may have a grade policy and grade predictor set on it. At present, we provide a ``SimpleTotalingGradingPolicy`` that may be used with any course, and a specialized policy that is only relevant to CS 1323. The grading policy calculates a predicted grade based on a student's performance in the course such that 0 <= predicted grade <= 1. This value is then interpreted by a grade scheme to produce a meaningful grade and displayed to be in an appropriate scale. (E.g. the ``LetterGradeScheme`` takes a predicted grade value of 0.75 and would convert it as a "C" assuming the default ranges are used.) This predicted and formatted grade is shown to students alongside their actual grades, and to instructors alongside each student's name in the gradebook.

In order for a course to provide predicted grades, it must have a grading policy and a grade scheme. The grading policy has a default grade scheme but may be changed using the "PresentationGradeScheme" property. Additionally, the course must have suitable assignments (auto-graded or no-submit assignments that have been graded by instructors, with total_points values specified), otherwise no grade can be predicted.

Simple totaling grading policy
------------------------------

This predicts a total grade for a student in a course based on the following formula:

Predicted grade = total possible points earned / total possible points

Total possible points earned is defined as the sum of the points of all assignments that:

* Have a total_points value defined
* Have autograding enabled or have a numerical assigned grade
* Are past the due date or have been assigned a grade by the instructor
* Have not been excused by the instructor
* Have been graded by an instructor if a no-submit assignment
* Have been submitted by the student before the due date

Total possible points are defined the same way but are not limited to submitted and graded assignments. This policy uses the LetterGradeScheme by default.

CS 1323 policy
--------------

Specialized and complicated policy only for use in the CS 1323 course


Grading schemes
---------------

We support various grade schemes, including letter grades, numeric grades, and boolean grades. 

Adding a grading scheme and policy to a course
==============================================

The views for the grading policy are defined in ``nti.app.products.gradebook.views.policy_views``. All views that modify the policy require admin authentication.

* Adding a policy for a course
	* POST to a context of an ``ICourseInstance`` or ``ICourseCatalogEntry``. 
	* Example: POST the json ``'{"Class" : "SimpleTotalGradingPolicy", "MimeType": "application/vnd.nextthought.gradebook.simpletotalinggradingpolicy"}'`` to ``/dataserver2/%2B%2Betc%2B%2Bhostsites/alpha.nextthought.com/%2B%2Betc%2B%2Bsite/Courses/Alpha/NTI%201000/GradingPolicy``

* Getting the policy
	* You can GET the policy for a course by sending a GET to the GradingPolicy view on the course link, or GET the policy directly by its ntiid.
	* If getting the policy from the course, send a GET to a link such as ``/dataserver2/%2B%2Betc%2B%2Bhostsites/alpha.nextthought.com/%2B%2Betc%2B%2Bsite/Courses/Alpha/NTI%201000/GradingPolicy`` (for the appropriate course).
	* If getting the policy directly, send a get directly to the policy. For example, sending a GET to ``/dataserver2/Objects/<ntiid_of_policy>``. 

* Modifying the policy 
	* You may PUT a new policy to an ``ICourseInstance`` or ``ICourseCatalogEntry``, or PUT directly to the policy itself if you know the NTIID of the policy. This would be useful if you wanted to change the grading scheme from the default one for a policy set on the course.
	* PUTting to the course would be similar to POSTing to it. Example: PUT the json ``'{"Class" : "SimpleTotalGradingPolicy", "MimeType": "application/vnd.nextthought.gradebook.simpletotalinggradingpolicy"}'`` to ``/dataserver2/%2B%2Betc%2B%2Bhostsites/alpha.nextthought.com/%2B%2Betc%2B%2Bsite/Courses/Alpha/NTI%201000/GradingPolicy`` in order to modify the policy on a course.
	* Example of PUTting directly to the policy: do a PUT to ``/dataserver2/Objects/<ntiid_of_policy>``

* Deleting the policy
	* You may send a DELETE to the GradingPolicy view on the course to delete the current policy, or to the policy itself.
	* Example: DELETE to ``/dataserver2/%2B%2Betc%2B%2Bhostsites/alpha.nextthought.com/%2B%2Betc%2B%2Bsite/Courses/Alpha/NTI%201000/GradingPolicy`` to delete the existing policy from a course.
	* Example of DELETEing directly to the policy: send a DELETE to ``/dataserver2/Objects/<ntiid_of_policy>``


Implementation notes
====================

Interfaces
----------

.. automodule:: nti.app.products.gradebook.interfaces
	:member-order: bysource


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
