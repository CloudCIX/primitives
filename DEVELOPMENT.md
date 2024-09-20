# Development

## Development Environment

When developing primitives, you can set up an editable development environment
on a CloudCIX Appliance or any machine that fullfils two requirements:

1) The ability to ssh to both of the environment's PodNet nodes and other
   relevant machines, such as hypervisors as the robot user in a passwordless
   manner.

2) A config.json for PodNet. On a CloudCIX Appliance you'll find this in
   `/etc/cloudcix/pod/configs/config.json`.

The the `tools/setup-testenv.sh` script will do all the neccessary setup steps for you.
Just point it at an empty or non-existent directory...

```
setup-testenv.sh myvenv
```

...and it will set up a development virtual environment for you. Once that is
done, you can activate the virtual environment as follows:

```
. myvenv/bin/activate
```

Now you can run test scripts such as `tools/test_ns_primitive.py` as long as
you remain in the shell where you sourced the `activate` script:

```
$ tools/test_ns_primitive.py build mytestns
Status: True

Message:
Successfully created network name space mytestns on both PodNet nodes.
```

You can mostly edit the code in this repository to your heart's content, commit
it and push it. The only problem arises when you add new files to the code
base. In this case, you have to run `pip install -e .` (substitute `.` by the
path to this repository as needed) again in the virtualenv. Otherwise, these
files will not be available.

## Helpers and Utilities

We have a small library of utility functions to make primitive development
easier. Refer to the inline documentation of `cloudcix_primitives.utils` to
learn about them.

## Templates

Right now, `cloudcix_primitives.ns` is our reference implementation for a
primitive. Please use this primitive as a template when developing new
primitives. Read below for patterns you should use.

### Patterns to use

#### RCC Wrappers

When running `cloudcix.rcc.*` functions, do not call them directly since they
take a lot of parameters which needlessly uses up a lot of screen space in your
primitive. Either use an existing wrapper such as
`cloudcix_primitives.utils.SSHCommsWrapper` or write your own if there's no
wrapper for the function you are using. The wrapper's purpose is to store the
parameters that are going to be identical every time you call the RCC function.

The only possible exception to that rule would be a very simple primitive where
you only ever call the RCC function once. In this case, there'd be zero benefit
in using a wrapper.

#### Error formatters

If you do your own error formatting, you will use a lot of screen space as
well. Again, use an existing error formatter such as
`cloudcix_primitives.utils.PodnetErrorFormatter` or write your own modelled on
that one. Since not all primitives are going to be operating on PodNet nodes,
we are eventually going to have to write different error formatters for e.g.
hypervisors.

Do not forget to use the formatter's `add_successful()` method after every
successfully run payload to record the payload's name and output. This adds
very valuable debugging information that can be useful in cases where a payload
was considered successful but actually did not actually bring about the outcome
it was supposed to bring about.

#### DRY (Do not Repeat Yourself)

In situations where you have to run the same set of payloads multiple times,
such as operations on PodNet nodes, try to avoid typing out that set of
instructions multiple times. You could use something like the inline
`run_podnet()` function in the `ns` primitive's verbs or come up with a
solution of your own.
