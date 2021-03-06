# awme
What is awme?
-------------
Great question! awme (pronounced "awe me") is a scalable, restful, hot cache of
your Amazon host and security group instance metadata!

awme consists of two main parts:

###amazon_metadata_collector.py
Fetches host and security group instance data using the AWS api (via boto) at a
configurable interval and serializes it to disk.

###restful_metadata_cache.py
Loads and periodically refreshes from pre-serialized metadata on disk and
serves it from memory as json from a restful api exposed via flask.

Amazon already has an api. Why does awme exist?
---------------------------------------
True Amazon has an API, but that API also has latency. Sometimes it's under one
second. Other times it can be a minute or more for each call. You could make
1000's of calls to awme in the same amount of time. There are also hard limits
on how frequently Amazon will allow you to call their api's. AwMe's only
restriction is what it can physically handle. If it's not enough for your use
case simply launch more instances and place them behind an ELB! :)

What are the requirements?
--------------------------
* Python 2.7
* Flask

How do I install?
-----------------
On amazon linux...
* sudo yum install git gcc
* sudo pip install Flask
* sudo pip install networkx
* sudo mkdir /opt/awme
* cd /opt/awme
* sudo git clone https://github.com/xavierpayne/awme.git

What is the license
-------------------
Apache 2.0
Read the full license here: https://github.com/sharethis-github/awme/blob/master/LICENSE ;)

What is unfinished/todo?
------------------------
The current version allows you to cache information from all regions you specify
in the config.ini file.

Where is the rest of the documentation!?
----------------------------
Like awme itself the documentation is currently a work in progress.
So don't taze me bro!

You should have better test coverage, docs, and support pip or easy_install!
----------------------------------------------------------------------------
Yeah, I know, right!? I'm a java guy and relatively new to Python so if you'd
care to help me out with that stuff drop me a line or better create a branch
and submit a pull request! :)

All right, who is responsible for this?
----------------------------
Primarily that would be me: [Christopher Vincelette](https://github.com/xavierpayne)
