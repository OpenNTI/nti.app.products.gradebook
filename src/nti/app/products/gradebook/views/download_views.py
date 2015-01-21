#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import csv
import nameparser
import collections
from cStringIO import StringIO

from zope import component

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users import User
from nti.dataserver import authorization as nauth
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalList

from ..utils import replace_username

from ..interfaces import IGradeBook
from ..interfaces import NO_SUBMIT_PART_NAME

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=IGradeBook,
			 permission=nauth.ACT_READ,
			 name='contents.csv')
class GradebookDownloadView(AbstractAuthenticatedView):
	"""
	Provides a downloadable table of all the assignments
	present in the gradebook. There is a column
	for each assignment and a row for each user.

	A query param `LegacyEnrollmentStatus` can be set to
	either 'ForCredit' or 'Open' to restrict the results to that
	subset of students.

	.. note:: This is hardcoded to export in D2L compatible format.
		(https://php.radford.edu/~knowledge/lore/attachment.php?id=57)
		Dialects would be easily possible.
	"""

	def _make_enrollment_predicate(self):
		status_filter = self.request.GET.get('LegacyEnrollmentStatus')
		if not status_filter:
			return lambda course, user: True

		def f(course,user):
			# TODO: Replace this with nti.contenttypes.courses.interfaces.ICourseInstanceEnrollmentRecord
			enrollment = component.queryMultiAdapter((course, user),
												   ICourseInstanceEnrollment)
			if enrollment is None:
				# We have a submitted assignment for a user no longer enrolled.
				return False
			return enrollment.LegacyEnrollmentStatus == status_filter # Let this blow up when this goes away
		return f

	def __call__(self):
		gradebook = self.request.context
		course = ICourseInstance(gradebook)
		predicate = self._make_enrollment_predicate()

		# We build a dictionary of {username: {Assignment: Grade} }
		# We keep track of known assignment names so we can sort appropriately;
		# it is keyed by the column name (as that's the only thing guaranteed
		# to be unique) and the value is the display name
		usernames_to_assignment_dict = collections.defaultdict(dict)
		seen_asg_names = dict()

		final_grade_entry = None

		for part in gradebook.values():
			for name, entry in part.items():
				if part.__name__ == NO_SUBMIT_PART_NAME and name == 'Final Grade':
					final_grade_entry = entry
					continue

				seen_asg_names[name] = entry.displayName or 'Unknown'
				for username, grade in entry.items():
					user_dict = usernames_to_assignment_dict[username]
					if name in user_dict:
						raise ValueError("Two entries in different part with same name")
					user_dict[name] = grade

		# Now, sort the *display* names, maintaining the
		# association to the actual part name
		sorted_asg_names = sorted((v, k) for k, v in seen_asg_names.items())

		# Now we can build up the rows.
		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context

		def _tx_string(s):
			# At least in python 2, the CSV writer only works
			# correctly with str objects, implicitly encoding
			# otherwise
			if isinstance(s, unicode):
				s = s.encode('utf-8')
			return s

		# First a header row.
		# Note that we are allowed to use multiple columns to identify
		# students
		rows.append( ['Username', 'External ID', 'First Name', 'Last Name', 'Full Name']
					 # Assignment names could theoretically have non-ascii chars
					 + [_tx_string(x[0]) + ' Points Grade' for x in sorted_asg_names]
					 + ['Adjusted Final Grade Numerator',
					 	'Adjusted Final Grade Denominator']
					 + ['End-of-Line Indicator'] )

		# Now a row for each user and each assignment in the same order.
		# Note that the webapp tends to send string values even when the user
		# typed a number: "75 -". For export purposes, if we can reverse that to a number,
		# we want it to be a number.
		def _tx_grade(value):
			if not isinstance(value, basestring):
				return value
			if value.endswith(' -'):
				try:
					return int(value[:-2])
				except ValueError:
					try:
						return float(value[:-2])
					except ValueError:
						return _tx_string(value)

		for username, user_dict in sorted(usernames_to_assignment_dict.items()):
			user = User.get_user(username)
			if not user or not predicate(course,user):
				continue

			profile = IUserProfile(user)
			external_id = replace_username(username)

			realname = profile.realname or ''
			if realname and '@' not in realname and realname != username:
				human_name = nameparser.HumanName( realname )
				firstname = human_name.first or ''
				lastname = human_name.last or ''
			else:
				firstname = ''
				lastname = ''

			data = (username, external_id, firstname, lastname, realname)
			row = [_tx_string(x) for x in data]
			for _, assignment in sorted_asg_names:
				grade = user_dict[assignment].value if assignment in user_dict else ""
				row.append(_tx_grade(grade))

			final_grade = final_grade_entry.get(username) if final_grade_entry else None
			row.append(_tx_grade(final_grade.value) if final_grade else 0)
			row.append( 100 )

			# End-of-line
			row.append('#')
			rows.append(row)

		# Anyone enrolled but not submitted gets a blank row
		# at the bottom...except that breaks the D2L model

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json or XLS alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		filename = course.__name__ + '-grades.csv'
		content_disposition = str( 'attachment; filename="%s"' % filename )
		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = content_disposition
		self.request.response.content_type = str( 'application/octet-stream' )
		return self.request.response
