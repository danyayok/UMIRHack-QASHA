import '../../static/global.css'
import '../../static/frontOver.css'

export default function FrontendOverview({ project }) {
    const testPercentage = project?.testPercentage || 40;
    const projectName = project?.name || 'Проект';
    const indicators = project?.indicators || [
        { name: 'Auth', status: 'completed' },
        { name: 'Market', status: 'in-progress' },
        { name: 'Tickets', status: 'not-started' }
    ];

    const getIndicatorColor = (status) => {
        switch (status) {
            case 'completed':
                return '#00FF00';
            case 'in-progress':
                return '#FFFF00';
            case 'not-started':
                return '#FF0000';
            default:
                return '#CCCCCC';
        }
    };

    return (
        <div className="tab-content">
            <div id='head-text-div'>
                <h1 id='head-text'>{projectName}</h1>
            </div>
            <div id='overview-div'>

                <div 
                    id='percentage-div'
                    style={{ 
                        background: `conic-gradient(#0268FB 0% ${testPercentage}%, white ${testPercentage}% 100%)` 
                    }}
                >
                    <h2 id='percent'>{testPercentage}%</h2>
                </div>

                <div id='div-for-indicators'>
                    {indicators.map((indicator, index) => (
                        <div key={index} className='indicator-div'>
                            <h2 className='ind-text'>{indicator.name}</h2>
                            <div 
                                className='tests-indicator'
                                style={{
                                    backgroundColor: getIndicatorColor(indicator.status),
                                    boxShadow: `0px 0px 4px 0px ${getIndicatorColor(indicator.status)}`
                                }}
                            ></div>
                        </div>
                    ))}
                </div>

            </div>

            <div id='tests-head-div'>
                <h2 id='tests-head'>Последние тесты</h2>
            </div>

            <div id='tests-div'>
                {project?.recentTests && (
                    <div>

                    </div>
                )}
            </div>
        </div>
    )
}