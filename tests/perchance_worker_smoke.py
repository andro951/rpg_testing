"""Real browser, simulated plugin: worker preserves whitespace, errors and cancellation."""
import os
from playwright.sync_api import sync_playwright
from workbench.perchance import WORKER


def main():
    with sync_playwright() as playwright:
        executable=os.environ.get('REPORT_BROWSER_EXECUTABLE')
        browser=playwright.chromium.launch(headless=True, **({'executable_path':executable} if executable else {}))
        page=browser.new_page()
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_content('<!doctype html><title>Text worker test</title>')
        page.evaluate('''() => { globalThis.root={aiTextPlugin:options=>{
            const pending=new Promise(resolve=>{globalThis.resolveJob=resolve;});
            pending.stop=()=>{globalThis.stopped=true;};
            options.onChunk({textChunk:"  RAW\\n"});
            return pending;
        }};}''')
        page.evaluate(WORKER.read_text(encoding='utf-8'))
        assert page.evaluate('() => RpgPerchanceText.Environment().ready')
        page.evaluate('() => RpgPerchanceText.Start({id:"a",instruction:"Prompt"})')
        assert page.evaluate('() => RpgPerchanceText.Snapshot("a").text')=='  RAW\n'
        page.evaluate('() => resolveJob({generatedText:"  RAW\\n",stopReason:"end"})')
        page.wait_for_function('RpgPerchanceText.Snapshot("a").state==="completed"')
        assert page.evaluate('() => RpgPerchanceText.Snapshot("a").text')=='  RAW\n'
        page.evaluate('() => RpgPerchanceText.Start({id:"b",instruction:"Prompt"})')
        page.evaluate('() => RpgPerchanceText.Cancel("b")')
        assert page.evaluate('() => stopped')
        page.evaluate('() => resolveJob({generatedText:"LATE",stopReason:"end"})')
        assert page.evaluate('() => RpgPerchanceText.Snapshot("b").text')=='  RAW\n'
        page.evaluate('() => RpgPerchanceText.Start({id:"c",instruction:"Prompt"})')
        page.evaluate('() => resolveJob({generatedText:"partial",stopReason:"error"})')
        page.wait_for_function('RpgPerchanceText.Snapshot("c").state==="error"')
        assert not errors, errors
        browser.close()
    print('Text-only worker browser smoke passed (simulated plugin)')


if __name__=='__main__':main()