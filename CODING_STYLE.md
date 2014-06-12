Share System team 2 coding style
================================
v.1.1

----

Use [PEP-8](http://legacy.python.org/dev/peps/pep-0008/ "PEP-8").

Automatic pep-8 checker:

    pip install pep8

    pep8 <file|directory>

Note: it's integrated inside the Pycharm IDE.

## Specific project conventions

### Strings and docstrings

We decided to use single apex for string literals:

    my_string = 'foo'  # easier to digit than "foo" :)

Docstrings always with triple double quotes (most standard):

    """
    My docstring.
    """

I noticed that Flask use to indent the content, but in my experience is not common.
And if you don't indent, you gain 4 spaces ;)

Tolerated:

    """Hello.
    """

or

    """Hello."""

Avoid:

    "Docstring." or 'Docstring.'


## Code example

    # !/usr/bin/env python
    # -*- coding: utf-8 -*-

    """
    The module docstring is here.
    """

    # If you have some imports from future, must be the first instructions.
    # Common examples are:
    from __future__ import print_function  # more flexible
    from __future__ import division  # 1 / 2 returns 0.5 instead of 0

    # First normal imports are from standard library.
    import os
    import shutil
    # Note: only one import per line is the PEP-8 standard.

    # Then the imports from 3rd parties modules (e.g. requests, watchdog, ...).
    import a_3rd_parties_module

    # Finally, your project imports.
    import my_module
    import my_other_module

    # Never use: from something import *

    # Comments
    # A complete sentence comment starts with a capital letter and ends with a period.

    # Constants are UPPERCASE with underscore
    A_CONSTANT = 1  # inline simple comment

    # Variables are lowercase with underscore
    my_variable = 1.2  # An inline comment sentence ending with a period.
    another_variable = 'a string'  # single apex


    def use_lowercase_with_underscore_for_functions(ok=True):
        """
        A useful function docstring.
        """
        pass


    def possibly_use_a_imperative_verb_in_a_function_name(arg, kwarg=0):
        # Is useful to quickly distinguish between a function and a variable.
        # Examples of variable: new_user, loaded_data
        # Example of functions: create_user, load_something
        # A common exception can be 'main'.
        pass


    def leave_2_blank_lines_between_main_module_function_or_classes():
        pass


    class AnExampleOfClass(object):
        """
        Class names use capitalized CamelCase.
        """

        def do_like_functions_for_methods(self):
            pass

        def but_left_only_one_blank_line_between_class_methods(self):
            pass


    # Class instances are variables.
    my_instance = AnExampleOfClass()


    # Never use 3 blank lines.
    ok = True


    if __name__ == '__main__':
        do_something()
