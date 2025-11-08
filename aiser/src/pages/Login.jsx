import '../static/login.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'
import MainButton from './components/MainButton'

export default function Login(){
    const navigate = useNavigate()

    const navigateButtonClick = (e) => {
        navigate('/Account')
        e.preventDefault();
    }
    return(
        <div id="travoman">
            <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id='logpan'>
                <h1 id='head-text'>Вход</h1>
                <form action="" id='form' onSubmit={navigateButtonClick}>
                    <input type="text"/>
                    <input type="password" id='passinput'/>
                    <button id='enter-button' type='submit'>Войти</button>
                </form>
                <div id='reglinkdiv'><Link to='/Registration' id='reglink'>У меня нет аккаунта</Link></div>
                
            </div>
        </div>
    )
}