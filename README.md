# awme
What is awme?
-------------
Great question! awme (pronounced "awe me") is a scalable, restful, hot cache of
your Amazon host and security group instance metadata!

awme consists of two main parts:

###amazon_metadata_collector
Fetches host and security group instance data using the AWS api (via boto) at a
configurable interval and serializes it to disk.

###restful_metadata_cache
Loads and periodically refreshes from pre-serialized metadata on disk and
serves it from memory as json from a restful api exposed via flask.

Amazon already has an api. Why does awme exist?
---------------------------------------
True Amazon has an API, but that API also has latency. Sometimes it's under one
second. Other times it can be a minute or more for each call. You could make
1000's of calls to awme in the same amount of time.

What are the requirements?
--------------------------
* Python 2.6
* Flask
* uwsgi
* nginex (or some other compatible server

What is the license
-------------------
Read the license: https://github.com/sharethis-github/awme/blob/master/LICENSE ;)

What is unfinished/todo?
------------------------
The current version is pre-release. It defaults to the region you run it in.
The first official release will actually allow you to cache information from
all regions you specify in the config.ini file.

Where is the rest of the documentation!?
----------------------------
Like awme the documentation is currently a work in progress.
So don't taze me bro!

You should have better test coverage, docs, and support pip or easy_install!
----------------------------------------------------------------------------
Yeah, I know, right!? I'm a java guy and relatively new to Python so if you'd
care to help me out with that stuff drop me a line or better create a branch
and submit a pull request! :)

All right, who is responsible for this?
----------------------------
Primarily that would be me: [Christopher Vincelette](https://github.com/xavierpayne)
