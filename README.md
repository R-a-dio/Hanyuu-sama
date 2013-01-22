# Introduction

The **Hanyuu-sama** project is a suit of applications that are used as the **R/a/dio** backend. This includes the **AFK streamer** and the **IRC Bot** among others. Below is given a detailed look at each component and what is expected from it.

**Completion:** Each Component will have a progression percentage that indicates how far the code base is in terms of completion from `1.2 > 1.3`. This percentage has no mathematical background and is just me making up numbers (They are fairly accurate though!).

**NOTE:** `Packages`, `Classes` and `Functions` mentioned in code blocks can be clicked on to go to their respective documentation on *readthedocs.org*.

# Documentation

The latest documentation is always available at [readthedocs][hanyuu].

We want to document as much as possible. If you want to help document pieces please do so. We use [**ReadTheDocs**][readthedocs] with [**Sphinx**][sphinx] documentation generation. 

Documentation files are contained in the `docs` directory in the repository. These are really only barebones to tell [Sphinx `autodoc`][sphinx.autodoc] to read the docstrings in the Python code.

Documentation relevant to code should be placed in a docstring in the source code rather than added to the `.rst` files in `docs`.

Documentation **not** relevant to any code should be placed in a `.rst` file in the `docs` directory together with a proper addition to the `index.rst`.

# Installation

Installation is currenty possible by using the following commands.

```
git clone https://github.com/R-a-dio/Hanyuu-sama.git
git checkout 1.3
cd Hanyuu-sama
python setup.py install
```

This will install all the required dependencies that we added to `setup.py` so far. The currently missing dependency is `pylibshout` which will be resolved soon.

**NOTE:** Right now the 1.3 branch is in no runable state. Don't try it's a wasted effort.

# Helping out

If you want to help develop you should create a fork of the repository on github. Then do a pull request when you finished working.

An outline of components and the plans/progress of each component is listed below for you.

Components
----------
  
Each component in the [`hanyuu`][hanyuu] package has a specific role to fulfill. This can range from simply tasks such as keeping check of *relay status* to the more complexer tasks of handling *audio data*. 

It is critical that a component only does the role it was designed for. This to reduce bugs, code duplication and structural integrity of the project.

This means that if a certain piece of code is *generic*, *small* and used by *many* of the sub modules it should be placed in the top package in a relevant named module (e.g. `hanyuu.utils` for small utility functions/classes.)

----

The following is a list of each application in the [`hanyuu`][hanyuu] package, any modules that are **not** named here and are in the [`hanyuu`][hanyuu] package should be regarded as *shared code* used by multiple applications.


### AFK Streamer [80% Complete]

The AFK streamer is contained in the [`hanyuu.streamer`][hanyuu.streamer] package and is arguably the most complex package.

It contains several sub packages:  
####[`hanyuu.streamer.audio`][hanyuu.streamer.audio][100% Complete]  

This package implements a simple *audio* pipeline. It is responsible for audio file *reading* and *decoding*, audio data *encoding* and audio data *output*.
    
The entry point of the whole package is the [`hanyuu.streamer.audio.Manager`][hanyuu.streamer.audio.manager] class that manages the audio pipeline. For more information see the documentation.

####[`hanyuu.streamer.audio.garbage`][hanyuu.streamer.audio.garbage][100% Complete]  

This package implements a simple, higher level *garbage collector*. 

We use this special *garbage collector* because the *audio* pipeline shouldn't be concerned about leaking garbage. By using an out-of-pipeline collector for this garbage we can keep the *audio* pipeline running cleanly.

Good examples are *encoder*, *decoder* and *icecast* instances that need to be cleanly shut down and collected after a restart of one such instance.

####[`hanyuu.streamer.afkstreamer`][hanyuu.streamer.afkstreamer][0% Complete]

This is the bridge between the AFK streamer [Queue][hanyuu.queue] and the [`hanyuu.streamer.audio`][hanyuu.streamer.audio] pipeline. It handles configuration and starting/stopping the pipeline.

### IRC Bot [70% Complete]
The *Hanyuu-sama* IRC Bot is contained in the [`hanyuu.ircbot`][hanyuu.ircbot] package and is composed of a generic IRC library and our own *handlers*. 

The IRC components should **NEVER** know that it is running *Hanyuu-sama* and should stay a generic IRC library.

####[`hanyuu.ircbot.irclib`][hanyuu.ircbot.irclib][100% Complete]
This is the generic IRC library, it currently supports most features exposed by the IRC protocol. The only stable feature missing is (X)DCC file transfers (which *Hanyuu-sama* does not use or need).

The entry point of this library is the [`hanyuu.ircbot.irclib.session.Session`][hanyuu.ircbot.irclib.session.Session] class.

**NOTE:** Even though this is noted at 100%, cleanup of the code base and/or class interfaces is possible.

####[`hanyuu.ircbot.commands`][hanyuu.ircbot.commands][0% Complete]
The IRC Handlers that actually interact with the user. These handlers should only **show** data and not **generate** any of it themself. This is to prevent the handlers from having actual logic in them. Generation of data should be done in the respective application sub-package and retrieved by API.

####plans:  

The commands module needs a rewrite to the new IRC library handler functionality. While we do this we should also make the handlers do as **little** as possible as spoken about in the above paragraph.

### Requests (Server) [0% Complete]

The requests are all handled in the [`hanyuu.requests`][hanyuu.requests] package. This includes *website* requests and *IRC* requests.


####plans:  

The package should contain a singular way to add a request to the **AFK Streamer** queue. The IRC Handler and CGI Server can then use that singular method to queue tracks. This so we have a single way of requesting instead of 1 for each method.

####[`hanyuu.requests.servers`][hanyuu.requests.servers][0% Complete]

This package contains all the available CGI Servers.

####plans:  

This package should contain all available CGI Servers, we prefer a FastCGI server and this is currently the only planned one to implement. 

Ideally running `python hanyuu.requests.servers --my options` should run the chosen CGI Server. Options should be taken from the configuration file while command line options should overwrite the configuration file options.

### Icecast Listener [90% Complete]

The icecast listener is contained in [`hanyuu.listener`][hanyuu.listener] and is responsible for listening in to the stream. This allows us to have a real-time view on the stream and acquire metadata as they are send to the users.

####plans:  

This package only requires a small cleanup and update to 1.3 communication, the listener functionality works fine.

**NOTE:** You are best off not touching this package till most of the other packages are finished since the functionality works, but the communication is not. Communication requires the other packages to be in a finished state.

### Status Access/Updater [99% Complete]

The status updater is responsible for keeping an eye out on relay status, server status, mount point status and more. 

Access to the status is done by the [`hanyuu.status`][hanyuu.status] module. This module is responsible for abstracting away the memcache/database server when reading state from other packages.

While the updater is contained in [`hanyuu.status.streamstatus`][hanyuu.status.streamstatus]. The updater is responsible for keeping the database up-to-date with the latest information.

####plans:

Right now the module works but can use a code clean-up. Especially [`hanyuu.status.streamstatus`][hanyuu.status.streamstatus] is mostly messy code that needs cleaning.

There is a possiblity that the **Icecast Listener** will be included in this package rather than being its own package. No conclusion has been found for this idea as of yet.

### Database Access [99% Complete]

Database access is done through [`hanyuu.db`][hanyuu.db] which contains [`peewee`][peewee] models to access the database. Using these models is discouraged in code, instead look at the **Abstraction** layer below.

####plans:

The module itself is practically done, it's possible that database tables we do use but don't have a model for yet exist. These should be added when they arise as problems.

### Abstraction Layer [70% Complete]

Contained in [`hanyuu.abstractions`][hanyuu.abstractions].

This is an abstraction layer for various data pieces we use. This is done so that the code is more *natural* and *pythonic*. It also allows us to easily change the underlying storage mechanism/form without rewriting code.

**NOTE:** API Changes in any of these modules should be carefully planned as to not rewrite/break working code just for a simple API change. Keep backwards compatibility if possible.

####plans:

The current code is working but might be incomplete. The easiest method we thought of was adding required abstractions as they arise in the other packages. 

Thus using any of the classes currently finished is encouraged, if you come across a case where you have to access the database/other data without an abstraction layer you should discuss this with Wessie or open an **Issue**.

[peewee]: https://github.com/coleifer/peewee
[hanyuu]: https://hanyuu-sama.readthedocs.org/en/latest/
[readthedocs]: https://readthedocs.org/

[sphinx]: http://sphinx-doc.org/
[sphinx.autodoc]: http://sphinx-doc.org/ext/autodoc.html#module-sphinx.ext.autodoc

[hanyuu.abstractions]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.abstractions.html

[hanyuu.db]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.db.html

[hanyuu.status]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.status.html
[hanyuu.status.streamstatus]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.status.streamstatus.html

[hanyuu.queue]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.queue.html

[hanyuu.requests]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.requests.html
[hanyuu.requests.servers]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.requests.servers.html

[hanyuu.listener]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.listener.html

[hanyuu.ircbot]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.ircbot.html
[hanyuu.ircbot.commands]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.ircbot.commands.html
[hanyuu.ircbot.irclib]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.ircbot.irclib.html
[hanyuu.ircbot.irclib.session.Session]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.ircbot.irclib.html#hanyuu.ircbot.irclib.session.Session

[hanyuu.streamer]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.streamer.html
[hanyuu.streamer.afkstreamer]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.streamer.afkstreamer.html
[hanyuu.streamer.audio]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.streamer.audio.html
[hanyuu.streamer.audio.garbage]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.streamer.audio.garbage.html
[hanyuu.streamer.audio.manager]: https://hanyuu-sama.readthedocs.org/en/latest/hanyuu.streamer.audio.html#hanyuu.streamer.audio.Manager
