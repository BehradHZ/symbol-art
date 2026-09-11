# symbol-art

Turn images into font-aware ASCII art — locally, from a terminal-style web UI or the CLI.

<img src="examples/behrad-input.jpg" width="360" alt="Example input portrait">

### Output

```text
                                                       
                            ,,                         
                      ,~*?*L"~"_.                      
                   ..'`-'':-,,'-?+_                    
                  :-.   `,__yyL_'*+"                   
                 `'-.  ,jgggggggp_,-_                  
                      '__`"ff""?fk`*/L                 
                     _(_"-_g&__]fg_``'.                
                    ,dgggR9B&&Bgggk,                   
                   `_f9M%n'"*=@Bggpy                   
                    ii?k___[QE_j&&P*                   
                     '"??fL[$gg&gp"                    
                      ,'""f%@BB@fr                     
                      |_.```'_]qgL                     
                      jyL__xgggg&[                     
                  ..'-byjLLaggggggk)~_,                
            ,,~;"''````*?hwdBBB@h?\_|/?7=+__           
         ,*\"",'"-,,,.... ````,__<+??l\/\*\*???=L_       
       ,""'*~"-.``'''''.,....'"""";___^"-;"*^???L.     
     .':':`;!_,,,......,,',,,,"-~__|<^*'_"'!\r><?},    
     '`-.'`!"\_,',,...,'',',:,-"~|**^|"_"'-*""\^v?L,   
   .,.,'.``;'"__'',,..,,`''''''-!""*^!_*'.,' '!/\+}<_  
   '-,.,.``:.`*>_.''.,--.`'.''',"""""""'.,' `,',*?L?l_ 
  ..,``-\ `",`'*\_,,''!_:.```'''--"_~~"'.'  `'_""_+\~| 
 ...!,.`!'`',.`'""!;_,~|!-.```.''''"_;-,:`  .,"~"_|"<^ 
.,.`'\,`'"``'..``'"""!"~*;,.````''''"~-''  ``-""",|"_7";
:_-.`|_.., ```````'','''""",...`````...,`   .,',~|<?^'|
""_,.'i_';    `````'-,.``'":...`````...'   `.'.,:_i?"'J
```

## Run

```bash
python -m pip install -r requirements.txt
python app.py
```

Windows: `app.cmd` · CLI: `python symbol_art.py image.png -w 60`
