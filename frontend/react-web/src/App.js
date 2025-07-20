/*********************************************************************************************************************
*  Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           *
*                                                                                                                    *
*  Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance        *
*  with the License. A copy of the License is located at                                                             *
*                                                                                                                    *
*      http://aws.amazon.com/asl/                                                                                    *
*                                                                                                                    *
*  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES *
*  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    *
*  and limitations under the License.                                                                                *
**********************************************************************************************************************/

/**
 * Main Application Component
 * 
 * This is the root component of the Virtual Banking Assistant application.
 * It handles user authentication through AWS Cognito and renders the main
 * content when authenticated.
 */

import { Authenticator } from '@aws-amplify/ui-react';
import Content from './Content'
import './App.css';

function App() {
    /**
     * Custom components for the Authenticator
     * Provides a branded header for the login screen
     */
    const components = {
        Header() {
            return (
                <div className='d-flex flex-column justify-content-center text-center'>
                    <p className='h1'>
                        Virtual Banking Assistant
                    </p>
                    <p className='h5 mb-5 text-secondary'>
                        Powered by Amazon Nova Sonic
                    </p>
                </div>
            );
        }
    }

    return (
        <div className='app'>
            <Authenticator
                loginMechanisms={['email']}  // Only allow email-based login
                components={components}      // Use custom components
                hideSignUp                   // Disable self-service sign up
            >
                {({ signOut, user }) => {
                    return <Content signOut={signOut} user={user} />
                }}
            </Authenticator>
        </div>
    );
}

export default App;
