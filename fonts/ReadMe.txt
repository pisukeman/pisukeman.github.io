
For information on these fonts, see my web page for this font pack:

WarGames Terminal Fonts By Michael Walden
 https://MW.Rat.bz/wgterm


License
-------
The WarGames font files in this pack (.TTF, .OTF, .FON, etc.) are my own work,
hereby licensed under a Creative Commons Attribution-NonCommercial-ShareAlike
4.0 International - CC BY-NC-SA 4.0 License.
https://CreativeCommons.org/licenses/by-nc-sa/4.0/


WarGames Terminal Font file creation steps
------------------------------------------

Below are notes on how I created the fonts in the WarGames Terminal Font font
pack.  There are more steps that I have omitted and I am saying that for now
those steps are outside the scope of this file.  I may expand with details
in a future revision of the font pack.  Most of the omitted details are in
the descriptions relative to FontForge.

The following three files are text files that I started with to create my
fonts.  Open them in a text editor to see the text character data.  I use
these files with ImageMagic and convert them to .PNG files using the
following example ImageMagic command:
 convert "WarGames Terminal N F.xpm" "WarGames Terminal N F.png"

WarGames Terminal N F.xpm
WarGames Terminal D F.xpm
WarGames Terminal R F.xpm

The .PNG files are then used as input to Fony by using:
File > Import > Bitmap Font Writer Font... > First Character: 32

WarGames Terminal D F.png
WarGames Terminal N F.png
WarGames Terminal R F.png

The following .FON files are then created using Fony:
File > Save As > Save as type [FON font container (*.fon)]
They are Microsoft Windows bitmapped font files for use with Windows programs.

WarGames Terminal N F.fon
WarGames Terminal D F.fon
WarGames Terminal R F.fon

The following .FNT font files are then created using Fony:
File > Save As > Save as type [FNT font resource (*.fnt)]
They are Microsoft Windows bitmapped font resource files used as input to
Bits'n'Picas.

WarGames Terminal D T.fnt
WarGames Terminal N T.fnt
WarGames Terminal R T.fnt

I use the above .FNT files as input into Bits'n'Picas using:
File > Open... > Select an encoding such as windows-1252
I then create the following temporary .TTF TrueType fonts using:
File > Export... > [TTF (TrueType) > [Export]
These temporary .TTF files need to be imported into FontForge to create new good
 looking .TTF files as follows:
Open Font > Specify temporary .TTF font file path and name > Click [OK]
Now, generate new .TTF files from FontForge as follows:
File > Generate Fonts... "WarGames Terminal D T.ttf" (Select TrueType below file name) - Click [Generate]
Now they are TrueType font files for use with your operating system's programs.

WarGames Terminal D T.ttf
WarGames Terminal N T.ttf
WarGames Terminal R T.ttf

With the .TTF files loaded in FontForge in the previous step, generate new .OTF files from FontForge as follows:
File > Generate Fonts... "WarGames Terminal D T.otf" (Select OpenType below file name) - Click [Generate]
The .OTF OpenType font files are for use with your operating system's programs.

WarGames Terminal D O.otf
WarGames Terminal N O.otf
WarGames Terminal R O.otf

With the .TTF files loaded in FontForge in the previous step, generate new .WOFF files from FontForge as follows:
File > Generate Fonts... "WarGames Terminal D T.woff" (Select Web Open Font (WOFF) below file name) - Click [Generate]
The .WOFF Web Open Font files are for use with your web browser in web pages that you create.
#### NOTE: Currently the generated .WOFF files do not work!  I am going to research this to figure out how to make
     them work and release a new WarGames Terminal Font font pack with this file updated and correct non-hacked .WOFF files.

WarGames Terminal N W.woff
WarGames Terminal D W.woff
WarGames Terminal R W.woff

The following three files are demonstrations of how to load the .WOFF fonts in HTML files you create.

WarGames Terminal N W Demo.htm
WarGames Terminal D W Demo.htm
WarGames Terminal R W Demo.htm

Tools used
----------
ImageMagick for text matrix (.xpm) to image (.png) conversion
 https://ImageMagick.org
Fony 1.4.7 by hukka for Bitmap font creation http://hukka.ncn.fi/?fony
Bits'n'Picas by Kreative Korp / Rebecca G. Bettencourt for Bitmap-to-outline
 vectorization https://GitHub.com/kreativekorp/bitsnpicas
FontForge by George Williams and the FontForge Project for TrueType font
 editing, fine-tuning, re-encoding etc. https://FontForge.org/en-US/

[]

