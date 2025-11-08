import '../static/reg.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'

export default function Registration(){
    const navigate = useNavigate()

    const navigateButtonClick = (e) => {
        navigate('/Login')
        e.preventDefault();
    }
    return(
        <div id="travoman">
        <div className='homelink'><Link to='/' className='home'>Главная</Link></div>
            <div id='logpan'>
                <h1 id='head-text'>Регистрация</h1>
                <form action="" id='form' onSubmit={navigateButtonClick}>
                    <input type="text"/>
                    <input type="text"/>
                    <input type="password" id='passinput'/>
                    <input type="password" id='passinputp'/>
                    <button id='enter-button' type='submit'>Зарегистрироваться</button>
                </form>
                <div id='loglinkdiv'><Link to='/Login' id='loglink'>У меня уже есть аккаунт</Link></div>
                
            </div>
        </div>
    )
}