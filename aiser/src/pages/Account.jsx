import '../static/account.css'
import '../static/global.css'
import { Link } from 'react-router-dom'

export default function Account(){

    return(
        <div id="travoman">
            <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id="account">
                <aside id="accountpanel">
                    <div id="ava">

                    </div>
                </aside>
                <div id='startdiv'><button id="start-test-button">Начать тест</button></div>
                <div className='cardsdiv' id='firstdiv'>
                    <div className='card'>

                    </div>
                    <div className='card'>

                    </div >
                    <div className='card'>
                        
                    </div>
                </div>
                <div className='cardsdiv' id='secdiv'>
                    <div className='card'>

                    </div>
                    <div className='card'>

                    </div >
                    <div className='card'>
                        
                    </div>
                </div>
            </div>
        </div>
    )
}