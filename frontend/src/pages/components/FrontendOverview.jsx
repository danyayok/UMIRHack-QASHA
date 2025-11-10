import '../../static/global.css'
import '../../static/frontOver.css'

export default function FrontendOverview() {
    return (
        <div className="tab-content">
            <div id='head-text-div'>
                <h1 id='head-text'>Проект 1</h1>
            </div>
            <div id='overview-div'>

                    <div id='percentage-div'>
                        <h2>40%</h2>
                    </div>

                <div id='div-for-indicators'>
                        <div className='indicator-div' id='auth-div'>
                            <h2>Auth</h2>
                            <div className='tests-indicator' id='auth-ind'></div>
                        </div>
                        <div className='indicator-div' id='market-div'>
                            <h2>Market</h2>
                            <div className='tests-indicator' id='market-ind'></div>
                        </div>
                        <div className='indicator-div' id='tickets-div'>
                            <h2>Tickets</h2>
                            <div className='tests-indicator' id='tickets-ind'></div>
                        </div>
                </div>

            </div>

            <div id='tests-head-div'>
                <h2 id='tests-head'>Последние тесты</h2>
            </div>

            <div id='tests-div'>

            </div>

        </div>
    )
}