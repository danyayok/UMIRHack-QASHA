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
            <Link id='logo-linkk' to='/'></Link>
            <div id='logpan'>
                <h1 id='head-text'>Регистрация</h1>
                <form action="" id='form' onSubmit={navigateButtonClick}>
                                <div className="reg-input-container">
                                    <input 
                                        type="text" 
                                        id='login-input'
                                        required
                                    />
                                    <label for="login-input">Логин</label>
                                </div>
                                <div className="reg-input-container">
                                    <input 
                                        type="text" 
                                        id='email-input'
                                        required
                                    />
                                    <label for="email-input">Почта</label>
                                </div>
                                <div className="reg-input-container">
                                    <input 
                                        type="password" 
                                        id='pass-input'
                                        required
                                    />
                                    <label for="pass-input">Пароль</label>
                                </div>
                                <div className="reg-input-container">
                                    <input 
                                        type="password" 
                                        id='sec-pass-input'
                                        required
                                    />
                                    <label for="sec-pass-input">Потвердите пароль</label>
                                </div>
                    
                    <button id='enter-button' type='submit'>Зарегистрироваться</button>
                </form>
                <div id='loglinkdiv'><Link to='/Login' id='loglink'>У меня уже есть аккаунт</Link></div>
                
            </div>
        </div>
    )
}