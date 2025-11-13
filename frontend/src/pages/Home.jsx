import '../static/home.css'
import '../static/global.css'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'


export default function Home(){
    const navigate = useNavigate()

    const navigateButtonClick = (e) => {
        navigate('/Login')
        e.preventDefault();
    }
    return(
        <div id="travoman">
            <div id="main-panel">
                <div id='links'>
                    <Link id='logo-link' to='/'></Link>
                    <div id='login'><Link className='links' to='/Login'>Вход</Link></div>
                    <div id='registration'><Link className='links' to='/Registration'>Регистрация</Link></div>
                </div>

                    <h1 id='qasha'>Qasha</h1>
                    <h1 id='shiza'>великая шиза</h1>
                    <p id='invisible'>No one hears a word they say. Has the memory gone? Are you feelin' numb? Not a word they say, but a voiceless crowd isn't backin' down</p>

                <button id='start-button' onClick={navigateButtonClick}>Начать</button>
                <div id='cardsdiv'>
                    <div className='cards'>
                        <p></p>
                    </div>
                    <div className='cards'>
                        <p></p>
                    </div>
                    <div className='cards'>
                        <p></p>
                    </div>
                    <div className='cards'>
                        <p></p>
                    </div>
                </div>
            </div>
        </div>
    )
}