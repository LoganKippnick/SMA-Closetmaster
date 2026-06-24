# WPI Student Music Association Virtual Quartermaster Assistant (AKA Mr. Blue Sky)
A Discord Bot for Worcester Polytechnic Institute (WPI) Student Music Association (SMA) server to assist the Quartermaster by managing gear requests and the closet
lockbox code.

## Description
Per the WPI Student Music Association constitution (as of April 10th, 2024), the role of the Quartermaster is defined as such:

> The Quartermaster is in charge of managing and maintaining the gear,
including at events unless responsibility is taken by another member. At
events, the quartermaster is expected to oversee the responsible and effective
use of the gear. They should be knowledgeable about the SMA’s gear and
know how to use it properly. The quartermaster has the responsibility of
keeping track of gear requests as well, and meeting with SMA members to
drop off / pick up gear.

This project offers a Discord Bot to assist the Quartermaster with such responsibilies by:
1. keeping track of the current lockbox code;
2. reminding the Quartermaster to change the lockbox code randomly once per week and providing a randomly-generated code;
3. sharing the lockbox code with bands before their scheduled rehearsal;
4. reminding bands for pictures of the gear closet before and after their scheduled rehearsal;
5. informing the Quartermaster of gear requests not associated with a band, whereby the Quartermaster must share the lockbox code themself;
6. rolling d20s, or any other dice;
7. and being polite (usually), among probably a few other things.

The bot is interacted with through commands that only execute if called by a a member of the Student Music Association Discord server with the "SMA Execs" role.
(Apart from the "roll" command, which by default rolls a single d20, as to not discourage the use of the bot in supposed D&D campaigns.) It uses the [WPI Student
Music Association public gear request Google Calendar](https://calendar.google.com/calendar/embed?src=b62f0ce688af06db86253c47daf6f972af67b0969e5965f776b1e4d077772b28%40group.calendar.google.com&ctz=America%2FNew_York)
to schedule messages to bands and the Quartermaster dependent on gear request information.

The Discord server and the Google Calendar are accessed via standard API calls. API tokens referenced by the program are stored in files that are not a part of
this repository.

## Authors
This project was devised, written, and is being maintained entirely by humans. Specifically, by one human in particular: Logan Kippnick ('27 RBE/CS), Vice President
of the SMA from B-term of 2024 to C-term of 2027.

## Acknowledgments
The development, maintenance, and use of this project was and is supported by the current officer board of the WPI Student Music Association to support its ongoing
mission to build a vibrant and welcoming campus community around music.

## Enabling Clause
This project abides by, and shall continue to abide by, the policies of Worcester Polytechnic Institute as well as all federal, state, and local laws. Any changes to this
project and/or its usage will follow, in word and spirit, all WPI policies and all federal, state, and local laws.
