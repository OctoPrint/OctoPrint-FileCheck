��          �               �  x   �  �  V  "    $  :  �   _     �  .        4     F  
   \  )   g  *   �  )   �     �     �                    1     >     [  �   s     /	  
   H	  �  S	  �  (     �  �  �  �   O  *  �  g    g  j  �   �  ,   �  F   �            
   2  2   =  6   p  .   �     �     �     �               5  (   =  *   f  �   �     k     �    �  �  �  	   q   
        The following checks are currently configured for your instance. You can enable or disable them as needed.
     
    The bundled File Check plugin allows checking your uploaded files for known slicer misconfigurations and related issues.
    The plugin automatically checks all freshly uploaded files and files selected for printing, but for already uploaded
    files you can also trigger a full file check manually. It is recommended to do this whenever new checks are added
    to the plugin, in which case your last check will be marked as outdated below.
 
    The bundled File Check plugin has been updated with new high priority checks. It is recommended to run a
    full file check now to ensure that you are aware of any critical issues in your uploaded files. Depending on the
    size of your upload folder, this may take several minutes.
 
    The bundled File Check plugin has been updated with new high priority checks. It is recommended to run a 
    full file check now to ensure that you are aware of any critical issues in your uploaded files. Depending on the 
    size of your upload folder, this may take several minutes.
 
    You can run a full file check by clicking the button below or alternatively at any time from the
    File Check plugin settings.
 A full File Check is suggested Allows to run File Check and view the results. Configured checks Current set of checks File Check File Check detected issues with %(path)s! File Check detected issues with this file! File Check detected the following issues: Full file check Last check: Leaked API Key Outdated Outdated set of checks Read more... Run File Check on all files? Run full file check now This will perform a check of all of your uploaded files for known issues. Depending on the amount of files this could take several minutes. It should not be done while a print is running. Travel Speed Placeholder Up to date Your file contains an API key that is not supposed to be there. This is caused by a bug in your slicer, and known to happen with PrusaSlicer (<= 2.1.1), BambuStudio (<= 1.8.4) and OrcaSlicer (<= 1.9.0). Do not share this file with anyone, update your slicer to a patched version immediately, and reslice your file. Also consider changing your API key in OctoPrint, as it might have been leaked by your slicer to third parties through any GCODE files shared previously. Your file still contains a place holder <code>{travel_speed}</code>. This is a common issue when using old start/stop GCODE code snippets in current versions of Cura, as the placeholder name switched to <code>{speed_travel}</code> at some point and no longer gets replaced in current versions. You need to fix this in your slicer and reslice your file, do not print it like it is as it will cause issues! unknown Project-Id-Version: OctoPrint-FileCheck 2024.3.27
Report-Msgid-Bugs-To: i18n@octoprint.org
POT-Creation-Date: 2024-03-27 11:40+0100
PO-Revision-Date: 2024-03-27 11:40+0100
Last-Translator: 
Language: de
Language-Team: de <LL@li.org>
Plural-Forms: nplurals=2; plural=(n != 1);
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
Generated-By: Babel 2.12.1
 
        Die folgenden Checks sind derzeit für deine Instanz konfiguriert. Du kannst sie bei Bedarf aktivieren oder deaktivieren.
     
    Das gebündelte File Check Plugin erlaubt das Prüfen deiner hochgeladenen Dateien auf bekannte Slicer Fehlkonfigurationen und
    damit zusammenhängende Probleme. Das Plugin prüft automatisch alle frisch hochgeladenen Dateien und Dateien, die zum Druck
    ausgewählt wurden, aber für bereits hochgeladene Dateienkannst du auch manuell einen vollständigen Datei-Check
    auslösen. Es wird empfohlen, dies zu tun, wann immer neue Checks zum Plugin hinzugefügt werden, in welchem Fall dein letzter Check
    unten als veraltet markiert wird.
 
    Das gebündelte File Check Plugin wurde mit neuen hochpriorisierten Checks aktualisiert. Es wird empfohlen, jetzt einen vollständigen
    Datei-Check durchzuführen, um sicherzustellen, dass du über kritische Probleme in deinen hochgeladenen Dateien informiert bist. Abhängig
    von der Größe deines Upload-Ordners kann das mehrere Minuten dauern.
 
    Das gebündelte File Check Plugin wurde mit neuen hochpriorisierten Checks aktualisiert. Es wird empfohlen, jetzt einen vollständigen
    Datei-Check durchzuführen, um sicherzustellen, dass du über kritische Probleme in deinen hochgeladenen Dateien informiert bist. Abhängig
    von der Größe deines Upload-Ordners kann das mehrere Minuten dauern.
 
    Du kannst einen vollständigen Datei-Check durchführen, indem du auf den unten stehenden Button klickst oder alternativ jederzeit
    über die Einstellungen des File Check Plugins.
 Ein vollständiger File Check wird empfohlen Erlaubt das Ausführen von File Check und das Anzeigen der Ergebnisse. Konfigurierte Checks Aktuelle Liste von Checks File Check File Check hat Probleme mit %(path)s festgestellt! File Check hat Probleme mit dieser Datei festgestellt! File Check hat folgende Probleme festgestellt: Vollständiger File Check Letzter check: Geleakter API Key Veraltet Veraltete Liste von Checks Mehr... File Check auf allen Dateien ausführen? Vollständigen File Check jetzt ausführen Das wird eine Prüfung aller deiner hochgeladenen Dateien auf bekannte Probleme durchführen. Abhängig von der Anzahl der Dateien kann das mehrere Minuten dauern. Es sollte nicht während eines Drucks gemacht werden. Travel Speed Platzhalter Aktuell Deine geslicete Datei beinhaltet einen API Schlüssel, der dort nicht sein sollte. Das wird durch einen Bug in deinem Slicer verursacht und ist bekannt bei PrusaSlicer (<= 2.1.1), BambuStudio (<= 1.8.4) und OrcaSlicer (<= 1.9.0). Teile diese Datei nicht mit anderen, aktualisiere deinen Slicer sofort auf eine gepatchte Version und slice die Datei erneut. Überlege auch, deinen API Schlüssel in OctoPrint zu ändern, da er durch deinen Slicer in vorher geteilten GCODE Dateien an Dritte weitergegeben worden sein könnte. Deine geslicete Datei beinhaltet den Platzhalter <code>{travel_speed}</code>. Das ist ein häufiges Problem wenn alter start/stop GCODE in aktuellen Versionen von Cura verwendet wird, da der Platzhaltername vor einiger Zeit zu <code>{speed_travel}</code> geändert wurde und die alte Variante in aktuellen Versionen nicht mehr ersetzt wird. Du musst das in deinem Slicer fixen und deine Datei erneut slicen. Versuche sie nicht so zu drucken, das wird Probleme verursachen! unbekannt 