Developer Guide
===============

Welcome to the DataMapPlot developer documentation! This guide will help you set up your development environment, understand the project structure, run tests, and contribute effectively to the project.



Ways to Contribute
------------------

Contributions of all kinds are welcome. Here are some of the ways that you can contribute to DataMapPlot:

1. **File an issue.** The easiest contribution to make is to `file an issue <https://github.com/TutteInstitute/datamapplot/issues/new>`_. Before filing an issue, please check the :ref:`FAQ<Frequently Asked Questions>`, and do a cursory search of `existing issues <https://github.com/TutteInstitute/datamapplot/issues?utf8=%E2%9C%93&q=is%3Aissue>`_. It also helps, but is not necessary, if you can provide clear instruction for how to reproduce a problem. If you have resolved an issue yourself please consider contributing to the :ref:`FAQ<Frequently Asked Questions>` so others can benefit from your work.
2. **Improve documentation.** Contributing to :ref:`documentation<Documentation>` is the easiest way to get started with development. Anything that `you` as a new user found hard to understand, or difficult to work out, is an excellent place to begin.
3. **Submit a PR.** :ref:`Code contributions<Development Workflow>` are always welcome, from simple bug fixes, to new features. The authors will endeavour to help walk you through any issues in the pull request discussion, so please feel free to open a pull request even if you are new to such things.
4. **Add an example.** :ref:`Examples<Creating Examples>` serve as both documentation and testable code. If you have a use case that you think would be helpful to others or would help to round out the test suite, please consider adding an example.

Development Setup
-----------------
Prerequisites
~~~~~~~~~~~~~

- Python 3.10 or newer (3.10, 3.11, or 3.12 recommended)
- Git
- Node.js for interactive tests

Development Environment Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using your preferred virtual environment:

1. **Clone the repository**

   .. code-block:: bash

      git clone https://github.com/TutteInstitute/datamapplot.git
      cd datamapplot

2. **Install Python dependencies**

   .. code-block:: bash

      # Install the package in development mode
      pip install -e .

      # Install testing dependencies
      pip install -r test-requirements.txt

      # For documentation development
      pip install -r doc/requirements.txt

3. **Install Node.js dependencies (for interactive tests)**

   .. code-block:: bash

      cd datamapplot/interactive_tests
      npm ci
      npx playwright install --with-deps

Project Structure
~~~~~~~~~~~~~~~~~

.. code-block:: none

   datamapplot/
   ├── datamapplot/                     # Main package source code
   │   ├── static/                      # Static assets (JS, CSS)
   │   ├── tests/                       # Python-based unit and static visual tests
   │   ├── interactive_tests/           # Playwright tests for interactive features
   ├── examples/                        # Example scripts showing usage
   ├── doc/                             # Documentation source files
   ├── azure-pipelines.yml              # CI configuration
   ├── azure-pipelines.screenshots.yml  # CI configuration for updating test baseline images
   ├── test-requirements.txt            # Testing dependencies
   ├── README.md                        # Project overview
   ├── LICENSE                          # License information
   ├── Makefile                         # Helper scripts for testing
   ├── setup.py                         # Package installation
   └── setup.cfg                        # Package metadata

Development Workflow
--------------------

Pull Request Process
~~~~~~~~~~~~~~~~~~~~

1. Fork the repository and create a branch
2. Make your changes and commit them
3. Run the tests locally and check the results
4. Create a pull request and make sure CI tests pass
5. Update baseline images if necessary
6. Address any feedback from code reviewers
7. Once approved, your changes will be merged

If you are fixing a known issue please add the issue number to the PR message. If you are fixing a new issue, feel free to file an issue and then reference it in the PR. You can `browse open issues <https://github.com/TutteInstitute/datamapplot/issues>`_ to find something to work on.

.. note::
   When runnning tests locally, the visual regression tests may not always pass as the snapshots are generated on the CI machines. If you are confident that the changes are correct, and you visually inspect the images that you're getting from your test failures are okay, you can proceed. If you are unsure, please ask for help in the PR.

Testing
-------

DataMapPlot has several types of tests:

1. **Unit tests**: Testing individual components
2. **Backend tests**: Testing the Python backend with pytest (these must be run before frontend tests)
3. **Static frontend tests**: Testing static plot outputs with pytest-mpl
4. **Interactive frontend tests**: Testing browser-based interactive features using playwright

There is a Makefile to simplify running the various kinds of tests and viewing the resulting reports. To access the available test rules, run ``make``. You'll see the following menu of available rules:

.. code-block:: none

    *** AVAILABLE RULES ***

    test                    Run all tests
    test-static             Run python based backend and static frontend tests
    test-backend            Run python based backend tests
    test-ui                 Run interactive frontend tests
    test-ui-fast            Run interactive frontend tests, not slow tests
    update-static-baseline  Update static baseline images
    report-static           Open the mpl static test report
    report-interactive      Open the playwright test report

Running Unit and Backend Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From the project root:

.. code-block:: bash

   make test-backend

This will run all of the unit tests and backend tests. These tests must be run before any interactive frontend tests as it generates the hmtl for the frontend tests.

Running Static Frontend Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These visual regression tests compare generated static outputs with baseline images using ``pytest-mpl``.

.. code-block:: bash

    # Run static tests
    make test-static

    # Open the mpl test report
    make report-static

If you make changes that impact the visual appearance of static outputs, you may need to update the baseline images. If tests fail with image differences, please review these results carefully to determine if the changes are expected.

Running Interactive Frontend Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The interactive tests use Playwright to test the browser-based interactive features:

.. code-block:: bash

    # Run all interactive tests
    make test-ui

    # Run only fast interactive tests
    make test-ui-fast

    # Open the playwright test report
    make report-interactive

If you make changes that affect the behaviour of interactive outputs, you may need to update the baseline images. If tests fail with image differences, please review these results carefully to determine if the changes are expected.

Interpreting Test Results
~~~~~~~~~~~~~~~~~~~~~~~~~

- **Unit test failures**: Check the test output for details on which tests failed
- **Static test failures**: Examine the difference images in the resulting test report
- **Interactive test failures**: Review the Playwright report for screenshots and error details

Both of the static and interactive tests compare the results againsts baseline images. If the changes are expected, you can update the baseline images using CI if needed.

Continuous Integration
----------------------

DataMapPlot uses `Azure Pipelines <https://dev.azure.com/TutteInstitute/build-pipelines/_build?definitionId=22>`_ for continuous integration testing.

CI Configuration
~~~~~~~~~~~~~~~~

The CI pipeline runs on:

- Multiple Python versions (3.10, 3.11, 3.12)
- Multiple platforms (macOS, Linux)

For each combination, it runs:

1. Python unit and visual tests
2. Interactive browser tests with Playwright

Finding Test Results in CI
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Go to the `Azure Pipelines page <https://dev.azure.com/TutteInstitute/build-pipelines/_build?definitionId=22>`_ for the repository
2. Select the build you're interested in
3. Navigate to the "Tests" tab to see test results
4. Static frontend test report artifacts are available under ``mpl-test-results-*``
5. Interactive frontend test report artifacts are available under ``playwright-report-*``

Handling CI Failures
~~~~~~~~~~~~~~~~~~~~

If your pull request fails tests in CI:

1. Click on the failing job to see detailed logs
2. For static frontend test failures, download the ``mpl-test-results-*`` artifacts and open the corresponding ``fig_comparion.html`` file
3. For interactive frontend test failures, download the ``playwright-report-*`` artifacts and open corresponding ``index.html`` file
4. Make necessary changes to fix the failures
5. Push your changes to update the pull request

.. note::
   If you're logged into Azure you can see the test results image diffs under the "Tests" tab, then under "Attachments" for the failing test.

Updating Baseline Images
~~~~~~~~~~~~~~~~~~~~~~~~
The static and interactive tests both compare the resutls to baseline images. If the changes are expected, you can update the baseline images using CI if needed.

The static baseline images are stored in the repository under ``datamapplot/tests/baseline_images/``.

The interactive baseline images are stored in the repository under ``datamapplot/interactive_tests/tests/<test-filename>-snapshots/``.

1. Run the `datamapplot-screenshot-generation pipeline <https://dev.azure.com/TutteInstitute/build-pipelines/_build?definitionId=30>`_ (Note: This pipeline must be triggered manually by a maintainer with access to Azure Pipelines. If you don't have access, ask a maintainer to run it for you.)
2. Download the artifacts from the run
3. Extract the images from the artifacts and commit them to the appropriate directory
4. Update your PR with the new baseline images

At this point, all of the tests should pass in CI with the new baseline images.

Creating Examples
-----------------

Examples serve as both documentation and testing. They can be found in the ``examples/`` directory and demonstrate usage patterns and help users understand the library's capabilities. Furthermore, examples are used as end-to-end tests to ensure that the library works as expected.

Example Structure
~~~~~~~~~~~~~~~~~

Each example should:

1. Include a descriptive docstring with a title and explanation
2. Be standalone and runnable
3. Use realistic but manageable data
4. Demonstrate a specific feature or use case

Adding an Example
~~~~~~~~~~~~~~~~~

1. Create a new Python file in the ``examples/`` directory with a descriptive name (e.g., ``plot_arxiv_ml.py``)
2. Follow the example structure outlined above
3. Make sure the example runs without errors
4. Add the example to the documentation
5. (Optional) Include the example in the CI pipeline as testable code

Documentation
-------------

Contributing to documentation is the easiest way to get started. Providing simple clear or helpful documentation for new users is critical. Anything that *you* as a new user found hard to understand, or difficult to work out, are excellent places to begin. Contributions to more detailed and descriptive error messages is especially appreciated. To contribute to the documentation please :ref:`pull request process<Pull Request Process>` (but you can ignore code test results).

DataMapPlot uses Sphinx with Read the Docs for documentation. Documentation is written in either reStructuredText format (.rst) or in jupyter notebooks (.ipynb)and stored in the ``doc/`` directory.

Building Documentation Locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install documentation dependencies
   pip install -r doc/requirements.txt

   # Build HTML documentation
   cd doc
   make html

   # View the documentation (open _build/index.html in a browser)


Writing Good Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~

- Use clear, concise language
- Include examples where appropriate
- Explain the "why" not just the "how"
- Keep API references up-to-date with code changes
- Include diagrams or screenshots for complex features


Troubleshooting
---------------

Getting Help
~~~~~~~~~~~~

- `Open an issue <https://github.com/TutteInstitute/datamapplot/issues/new>`_ on GitHub
- Ask questions in :ref:`pull requests<Pull Request Process>`
- Check existing documentation (e.g. :ref:`FAQ<Frequently Asked Questions>`, :ref:`examples<Creating Examples>`)

Helpful Resources
~~~~~~~~~~~~~~~~~

- `NumPy Docstring Guide <https://numpydoc.readthedocs.io/en/latest/format.html>`_
- `Sphinx Documentation <https://www.sphinx-doc.org/>`_
- `Playwright Testing <https://playwright.dev/>`_
- `Azure Pipelines Documentation <https://learn.microsoft.com/en-us/azure/devops/pipelines/>`_