#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import argparse
import importlib

from nti.app.products.gradebook.grading.utils import calculate_grades

from nti.app.products.gradebook.interfaces import IGradeScheme

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


def _process_args(ntiid, scheme=None, usernames=(), site=None,
                  entry_name=None, verbose=False):
    if scheme:
        module_name, class_name = scheme.rsplit(".", 1)
        module = importlib.import_module(module_name)
        grade_scheme = getattr(module, class_name)()
        if not IGradeScheme.providedBy(grade_scheme):
            raise ValueError("Invalid grade scheme class")
    else:
        grade_scheme = None

    set_site(site)
    context = find_object_with_ntiid(ntiid)
    course = ICourseInstance(context, None)
    if course is None:
        raise ValueError("Course not found", ntiid)

    usernames = {x.lower() for x in usernames or ()}
    result = calculate_grades(course,
                              usernames=usernames,
                              grade_scheme=grade_scheme,
                              entry_name=entry_name,
                              verbose=verbose)
    if not entry_name or verbose:
        print("\nGrades...")
        for name, grade in result.items():
            print("\t", name, grade.value)
    return result


def main():
    arg_parser = argparse.ArgumentParser(description="Grade calculator")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose",
                            action='store_true', dest='verbose')
    arg_parser.add_argument('ntiid', help="Course NTIID")

    arg_parser.add_argument('-s', '--site', dest='site',
                            help="Request site")

    arg_parser.add_argument('-g', '--grade', dest='scheme',
                            help="Grade scheme class name")

    arg_parser.add_argument('-e', '--entry', dest='entry',
                            help="Grade entry name")

    arg_parser.add_argument('-u', '--users',
                            dest='usernames',
                            nargs="+",
                            default=(),
                            help="The usernames")
    args = arg_parser.parse_args()
    verbose = args.verbose

    site = args.site
    if not site and verbose:
        print('WARN: NO site specified')

    env_dir = os.getenv('DATASERVER_DIR')
    context = create_context(env_dir, with_library=True)
    conf_packages = ('nti.appserver',)
    run_with_dataserver(environment_dir=env_dir,
                        verbose=verbose,
                        context=context,
                        minimal_ds=True,
                        xmlconfig_packages=conf_packages,
                        function=lambda: _process_args(site=site,
                                                       verbose=verbose,
                                                       ntiid=args.ntiid,
                                                       scheme=args.scheme,
                                                       entry_name=args.entry,
                                                       usernames=args.usernames))


if __name__ == '__main__':
    main()
