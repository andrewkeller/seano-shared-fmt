Shared Code used by Seano Views
===============================

This repository contains shared code used by a number of Seano views.  The code
in this repository is intended to be _**vendored into its immediate usage**_,
rather than being a standalone PyPI module.  This approach is intended to help
avoid unexpected breakages in existing Seano views just because a new version of
this shared code was published.

Presently, this project has no CI of its own.  This is not desirable, and we
hope it will change in the future.  For now, the CI for the usages of this
library are expected to cover all the testing needs for this repository.
