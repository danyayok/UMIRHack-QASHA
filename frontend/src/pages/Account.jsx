import '../static/account.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import MainButton from './components/MainButton'
import { useState } from 'react'

export default function Account(){
    const [isListVisible, setIsListVisible] = useState(false)

    const toggleList = () => {
        setIsListVisible(!isListVisible)
    }
    return(
        <div id="travoman">
            <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id="account">
                <aside id="accountpanel">
                    <div id="user">
                        <div id='ava'></div>
                        <div id='user-name'></div>
                        
                    </div>
                    <div id='projects'>
                        <button id='buttproj' onClick={toggleList}><p id='butt-sign' >Проекты</p></button>
                        <ul id='list' className={isListVisible ? 'visible' : 'hidden'}>
                            <li>ТГ-бот для пивнухи</li>
                        </ul>
                    </div>
                </aside>

                <div className='cardsdiv' id='firstdiv'>

                    <div className='card' id='card1'>
                        <div id='card-name-div'><p id='card-name'>ТГ-бот для пивнухи</p></div>
                        <div id='bottom-row'>
                            <Link to='/' id='gear'/>
                            <div id='indicator'></div>
                        </div>
                    </div>

                    <div className='card'>
                        <button id="add-project"></button>
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